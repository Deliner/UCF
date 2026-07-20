package main

import (
	"crypto/sha256"
	"debug/buildinfo"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path/filepath"
	"syscall"
)

type verificationExecutableSnapshot struct {
	path       string
	root       string
	digest     string
	size       int
	modulePath string
}

func prepareVerificationExecutableSnapshot(
	sourcePath string,
	procedure verificationProcedureSpec,
) (*verificationExecutableSnapshot, error) {
	return prepareVerificationExecutableSnapshotWithCleanup(
		sourcePath,
		procedure,
		func(snapshot *verificationExecutableSnapshot) error {
			return snapshot.cleanup()
		},
	)
}

func prepareVerificationExecutableSnapshotWithCleanup(
	sourcePath string,
	procedure verificationProcedureSpec,
	cleanup func(*verificationExecutableSnapshot) error,
) (*verificationExecutableSnapshot, error) {
	snapshot, err := copyVerificationExecutableSnapshot(sourcePath)
	if err != nil {
		return nil, err
	}
	info, infoErr := buildinfo.ReadFile(snapshot.path)
	if infoErr != nil || !validVerificationBuildInfo(
		info,
		procedure.fixtureModulePath,
	) {
		cleanupErr := cleanup(snapshot)
		return nil, errors.Join(
			errors.New("unsupported fixture build"),
			cleanupErr,
		)
	}
	snapshot.modulePath = procedure.fixtureModulePath
	return snapshot, nil
}

func copyVerificationExecutableSnapshot(
	sourcePath string,
) (
	result *verificationExecutableSnapshot,
	resultErr error,
) {
	canonicalPath, err := strictFixtureExecutable(sourcePath)
	if err != nil {
		return nil, err
	}
	before, err := os.Lstat(canonicalPath)
	if err != nil {
		return nil, errors.New("fixture executable is unavailable")
	}
	sourceDescriptor, err := syscall.Open(
		canonicalPath,
		syscall.O_RDONLY|syscall.O_CLOEXEC|syscall.O_NOFOLLOW,
		0,
	)
	if err != nil {
		return nil, errors.New("fixture executable cannot be opened safely")
	}
	source := os.NewFile(uintptr(sourceDescriptor), canonicalPath)
	if source == nil {
		_ = syscall.Close(sourceDescriptor)
		return nil, errors.New("fixture executable cannot be opened safely")
	}
	defer source.Close()

	opened, err := source.Stat()
	if err != nil ||
		!opened.Mode().IsRegular() ||
		opened.Mode()&0111 == 0 ||
		opened.Size() < 1 ||
		opened.Size() > maxVerificationExecutableBytes ||
		!sameStableExecutableInfo(before, opened) {
		return nil, errors.New("fixture executable changed before snapshot")
	}

	root, err := os.MkdirTemp("", "ucf-go-verification-executable-")
	if err != nil {
		return nil, err
	}
	snapshot := &verificationExecutableSnapshot{
		path: filepath.Join(root, "fixture"),
		root: root,
	}
	failed := true
	defer func() {
		if failed {
			result = nil
			resultErr = cleanupIncompleteVerificationExecutableSnapshot(
				snapshot,
				resultErr,
			)
		}
	}()

	destination, err := os.OpenFile(
		snapshot.path,
		os.O_WRONLY|os.O_CREATE|os.O_EXCL,
		0600,
	)
	if err != nil {
		return nil, err
	}
	hasher := sha256.New()
	copied, copyErr := io.Copy(
		io.MultiWriter(destination, hasher),
		io.LimitReader(source, maxVerificationExecutableBytes+1),
	)
	syncErr := destination.Sync()
	closeErr := destination.Close()
	afterOpen, statErr := source.Stat()
	afterPath, pathErr := os.Lstat(canonicalPath)
	if copyErr != nil ||
		syncErr != nil ||
		closeErr != nil ||
		statErr != nil ||
		pathErr != nil ||
		copied != opened.Size() ||
		copied < 1 ||
		copied > maxVerificationExecutableBytes ||
		!sameStableExecutableInfo(opened, afterOpen) ||
		!sameStableExecutableInfo(afterOpen, afterPath) {
		return nil, errors.New("fixture executable changed during snapshot")
	}
	if err := os.Chmod(snapshot.path, 0500); err != nil {
		return nil, err
	}
	snapshot.digest = hex.EncodeToString(hasher.Sum(nil))
	snapshot.size = int(copied)
	failed = false
	return snapshot, nil
}

func cleanupIncompleteVerificationExecutableSnapshot(
	snapshot *verificationExecutableSnapshot,
	operationErr error,
) error {
	return errors.Join(operationErr, snapshot.cleanup())
}

func sameStableExecutableInfo(left os.FileInfo, right os.FileInfo) bool {
	leftStat, leftOK := left.Sys().(*syscall.Stat_t)
	rightStat, rightOK := right.Sys().(*syscall.Stat_t)
	return leftOK &&
		rightOK &&
		left.Mode() == right.Mode() &&
		left.Size() == right.Size() &&
		left.ModTime().Equal(right.ModTime()) &&
		leftStat.Dev == rightStat.Dev &&
		leftStat.Ino == rightStat.Ino &&
		leftStat.Ctim == rightStat.Ctim
}

func (snapshot *verificationExecutableSnapshot) cleanup() error {
	if snapshot == nil || snapshot.root == "" {
		return nil
	}
	if err := os.RemoveAll(snapshot.root); err != nil {
		return errors.Join(
			errVerificationCleanup,
			errors.New("verification executable snapshot cleanup failed"),
			err,
		)
	}
	snapshot.root = ""
	snapshot.path = ""
	return nil
}
