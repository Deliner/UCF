package main

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
)

const prSetChildSubreaper = 36

var (
	verificationSubreaperOnce sync.Once
	verificationSubreaperErr  error
)

type verificationProcessIdentity struct {
	processID int
	startTime uint64
}

type verificationProcessOwner struct {
	root     verificationProcessIdentity
	baseline map[int]verificationProcessIdentity
	tracked  map[int]verificationProcessIdentity
}

func ensureVerificationSubreaper() error {
	verificationSubreaperOnce.Do(func() {
		_, _, errno := syscall.Syscall6(
			syscall.SYS_PRCTL,
			prSetChildSubreaper,
			1,
			0,
			0,
			0,
			0,
		)
		if errno != 0 {
			verificationSubreaperErr = errno
		}
	})
	return verificationSubreaperErr
}

func startVerificationProcess(
	command *exec.Cmd,
) (*verificationProcessOwner, error) {
	if command == nil {
		return nil, errors.New("verification command is unavailable")
	}
	if err := ensureVerificationSubreaper(); err != nil {
		return nil, err
	}
	baseline, err := directVerificationChildren()
	if err != nil {
		return nil, err
	}
	if err := command.Start(); err != nil {
		return nil, err
	}
	root, exists, identityErr := readVerificationProcessIdentity(
		command.Process.Pid,
	)
	if identityErr != nil || !exists {
		_ = syscall.Kill(-command.Process.Pid, syscall.SIGKILL)
		_ = command.Process.Kill()
		_ = command.Wait()
		if identityErr != nil {
			return nil, identityErr
		}
		return nil, errors.New("verification process identity is unavailable")
	}
	return &verificationProcessOwner{
		root:     root,
		baseline: baseline,
		tracked: map[int]verificationProcessIdentity{
			root.processID: root,
		},
	}, nil
}

func (owner *verificationProcessOwner) signal(
	signal syscall.Signal,
) error {
	return owner.signalTracked(signal, true)
}

func (owner *verificationProcessOwner) signalDescendants(
	signal syscall.Signal,
) error {
	return owner.signalTracked(signal, false)
}

func (owner *verificationProcessOwner) signalTracked(
	signal syscall.Signal,
	includeRoot bool,
) error {
	if owner == nil {
		return nil
	}
	if err := owner.refresh(); err != nil {
		return err
	}
	var signalErr error
	for _, identity := range owner.tracked {
		if !includeRoot && identity.processID == owner.root.processID {
			continue
		}
		current, exists, err := readVerificationProcessIdentity(
			identity.processID,
		)
		if err != nil {
			signalErr = errors.Join(signalErr, err)
			continue
		}
		if !exists || current.startTime != identity.startTime {
			continue
		}
		if err := syscall.Kill(identity.processID, signal); err != nil &&
			!errors.Is(err, syscall.ESRCH) {
			signalErr = errors.Join(signalErr, err)
		}
	}
	return signalErr
}

func (owner *verificationProcessOwner) descendantsGone() (bool, error) {
	if owner == nil {
		return true, nil
	}
	if err := owner.refresh(); err != nil {
		return false, err
	}
	if err := owner.reapAdoptedChildren(); err != nil {
		return false, err
	}
	for processID, identity := range owner.tracked {
		if processID == owner.root.processID {
			continue
		}
		current, exists, err := readVerificationProcessIdentity(processID)
		if err != nil {
			return false, err
		}
		if exists && current.startTime == identity.startTime {
			return false, nil
		}
	}
	return true, nil
}

func (owner *verificationProcessOwner) refresh() error {
	queue := make([]verificationProcessIdentity, 0, len(owner.tracked))
	for _, identity := range owner.tracked {
		current, exists, err := readVerificationProcessIdentity(
			identity.processID,
		)
		if err != nil {
			return err
		}
		if exists && current.startTime == identity.startTime {
			queue = append(queue, identity)
		}
	}
	direct, err := directVerificationChildren()
	if err != nil {
		return err
	}
	for processID, identity := range direct {
		baselineIdentity, baselineMatch := owner.baseline[processID]
		if baselineMatch &&
			baselineIdentity.startTime == identity.startTime {
			continue
		}
		trackedIdentity, tracked := owner.tracked[processID]
		if !tracked || trackedIdentity.startTime != identity.startTime {
			owner.tracked[processID] = identity
			queue = append(queue, identity)
		}
	}
	visited := map[int]bool{}
	for len(queue) > 0 {
		identity := queue[0]
		queue = queue[1:]
		if visited[identity.processID] {
			continue
		}
		visited[identity.processID] = true
		children, err := verificationChildren(identity.processID)
		if err != nil {
			return err
		}
		for processID, child := range children {
			trackedIdentity, tracked := owner.tracked[processID]
			if !tracked ||
				trackedIdentity.startTime != child.startTime {
				owner.tracked[processID] = child
				queue = append(queue, child)
			}
		}
	}
	return nil
}

func (owner *verificationProcessOwner) reapAdoptedChildren() error {
	for processID := range owner.tracked {
		if processID == owner.root.processID {
			continue
		}
		var status syscall.WaitStatus
		waited, err := syscall.Wait4(
			processID,
			&status,
			syscall.WNOHANG,
			nil,
		)
		if err != nil &&
			!errors.Is(err, syscall.ECHILD) &&
			!errors.Is(err, syscall.ESRCH) {
			return err
		}
		if err != nil {
			continue
		}
		if waited != 0 && waited != processID {
			return errors.New("unexpected verification child was reaped")
		}
	}
	return nil
}

func directVerificationChildren() (
	map[int]verificationProcessIdentity,
	error,
) {
	return verificationChildren(os.Getpid())
}

func verificationChildren(
	processID int,
) (map[int]verificationProcessIdentity, error) {
	taskPaths, err := filepath.Glob(
		"/proc/" + strconv.Itoa(processID) + "/task/*/children",
	)
	if err != nil {
		return nil, err
	}
	result := map[int]verificationProcessIdentity{}
	for _, taskPath := range taskPaths {
		payload, readErr := os.ReadFile(taskPath)
		if verificationProcessDisappeared(readErr) {
			continue
		}
		if readErr != nil {
			return nil, readErr
		}
		for _, value := range strings.Fields(string(payload)) {
			childID, parseErr := strconv.Atoi(value)
			if parseErr != nil || childID < 1 {
				return nil, errors.New(
					"verification child identity is invalid",
				)
			}
			identity, exists, identityErr :=
				readVerificationProcessIdentity(childID)
			if identityErr != nil {
				return nil, identityErr
			}
			if exists {
				result[childID] = identity
			}
		}
	}
	return result, nil
}

func readVerificationProcessIdentity(
	processID int,
) (verificationProcessIdentity, bool, error) {
	payload, err := os.ReadFile(
		"/proc/" + strconv.Itoa(processID) + "/stat",
	)
	if verificationProcessDisappeared(err) {
		return verificationProcessIdentity{}, false, nil
	}
	if err != nil {
		return verificationProcessIdentity{}, false, err
	}
	closing := strings.LastIndex(string(payload), ") ")
	if closing < 1 {
		return verificationProcessIdentity{}, false, errors.New(
			"verification process identity is malformed",
		)
	}
	fields := strings.Fields(string(payload)[closing+2:])
	if len(fields) <= 19 {
		return verificationProcessIdentity{}, false, errors.New(
			"verification process identity is incomplete",
		)
	}
	startTime, err := strconv.ParseUint(fields[19], 10, 64)
	if err != nil {
		return verificationProcessIdentity{}, false, errors.New(
			"verification process start time is invalid",
		)
	}
	return verificationProcessIdentity{
		processID: processID,
		startTime: startTime,
	}, true, nil
}

func verificationProcessDisappeared(err error) bool {
	return errors.Is(err, os.ErrNotExist) ||
		errors.Is(err, syscall.ESRCH)
}
