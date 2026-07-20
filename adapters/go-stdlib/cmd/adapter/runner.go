package main

import (
	"context"
)

type operationOutcome struct {
	result                    map[string]any
	code                      string
	message                   string
	cancellationCleanupFailed bool
}

type operationJob struct {
	id        string
	method    string
	payload   map[string]any
	context   context.Context
	cancel    context.CancelFunc
	started   bool
	cancelled bool
	block     bool
}

func successfulOperation(result map[string]any) operationOutcome {
	return operationOutcome{result: result}
}

func failedOperation(code string, message string) operationOutcome {
	return operationOutcome{code: code, message: message}
}

func cancelledOperation() operationOutcome {
	return failedOperation(
		"request_cancelled",
		"adapter request was cancelled",
	)
}

func cleanupFailedOperation(message string) operationOutcome {
	return operationOutcome{
		code:                      "operation_failed",
		message:                   message,
		cancellationCleanupFailed: true,
	}
}

func (instance *server) startOperationRunner() {
	instance.operationMu.Lock()
	defer instance.operationMu.Unlock()
	instance.operationCond = syncNewCond(&instance.operationMu)
	instance.operationJobs = map[string]*operationJob{}
	instance.operationDone = make(chan struct{})
	go instance.runOperationLoop()
}

func (instance *server) stopOperationRunner() {
	instance.operationMu.Lock()
	if instance.operationCond == nil || instance.operationStopping {
		done := instance.operationDone
		instance.operationMu.Unlock()
		if done != nil {
			<-done
		}
		return
	}
	instance.operationStopping = true
	for id, job := range instance.operationJobs {
		job.cancelled = true
		job.cancel()
		if !job.started {
			delete(instance.operationJobs, id)
		}
	}
	instance.operationQueue = nil
	instance.operationCond.Broadcast()
	done := instance.operationDone
	instance.operationMu.Unlock()
	<-done
}

func (instance *server) enqueueOperation(
	id string,
	method string,
	payload map[string]any,
	block bool,
) bool {
	contextValue, cancel := context.WithCancel(context.Background())
	job := &operationJob{
		id:      id,
		method:  method,
		payload: payload,
		context: contextValue,
		cancel:  cancel,
		block:   block,
	}
	instance.operationMu.Lock()
	defer instance.operationMu.Unlock()
	if instance.operationStopping ||
		len(instance.operationJobs) >= maxPending {
		cancel()
		return false
	}
	instance.operationJobs[id] = job
	instance.operationQueue = append(instance.operationQueue, job)
	instance.operationCond.Signal()
	return true
}

func (instance *server) runOperationLoop() {
	defer close(instance.operationDone)
	for {
		instance.operationMu.Lock()
		for len(instance.operationQueue) == 0 &&
			!instance.operationStopping {
			instance.operationCond.Wait()
		}
		if instance.operationStopping &&
			len(instance.operationQueue) == 0 {
			instance.operationMu.Unlock()
			return
		}
		job := instance.operationQueue[0]
		instance.operationQueue[0] = nil
		instance.operationQueue = instance.operationQueue[1:]
		current, active := instance.operationJobs[job.id]
		if !active || current != job {
			instance.operationMu.Unlock()
			continue
		}
		job.started = true
		instance.operationMu.Unlock()

		var outcome operationOutcome
		if job.block {
			<-job.context.Done()
		} else {
			outcome = instance.runProductOperation(job)
		}

		instance.completeOperation(job, outcome)
	}
}

func (instance *server) completeOperation(
	job *operationJob,
	outcome operationOutcome,
) {
	instance.operationMu.Lock()
	defer instance.operationMu.Unlock()
	current, active := instance.operationJobs[job.id]
	if !active || current != job {
		return
	}
	if !instance.operationStopping {
		if job.cancelled && !outcome.cancellationCleanupFailed {
			instance.writeError(
				job.id,
				"request_cancelled",
				"adapter request was cancelled",
			)
		} else {
			instance.writeOperationOutcome(job.id, outcome)
		}
	}
	delete(instance.operationJobs, job.id)
	job.cancel()
}

func (instance *server) runProductOperation(
	job *operationJob,
) operationOutcome {
	switch job.method {
	case "ucf.inventory":
		return instance.inventory(job.context, job.payload)
	case "ucf.discover":
		return instance.discovery(job.context, job.payload)
	case "ucf.map":
		return instance.mapping(job.context, job.payload)
	case "ucf.verify":
		return instance.verification(job.context, job.payload)
	default:
		return failedOperation(
			"operation_failed",
			"operation runner has no product handler",
		)
	}
}

func (instance *server) writeOperationOutcome(
	id string,
	outcome operationOutcome,
) {
	if outcome.code != "" {
		instance.writeError(id, outcome.code, outcome.message)
		return
	}
	if outcome.result == nil {
		instance.writeError(
			id,
			"internal_error",
			"operation returned no terminal outcome",
		)
		return
	}
	instance.write(map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"result":  outcome.result,
	})
}

func (instance *server) cancelOperation(id string) {
	instance.operationMu.Lock()
	job, active := instance.operationJobs[id]
	if !active {
		instance.operationMu.Unlock()
		return
	}
	job.cancelled = true
	job.cancel()
	if job.started && !job.block {
		instance.operationMu.Unlock()
		return
	}
	if !job.started {
		for index, queued := range instance.operationQueue {
			if queued == job {
				copy(
					instance.operationQueue[index:],
					instance.operationQueue[index+1:],
				)
				last := len(instance.operationQueue) - 1
				instance.operationQueue[last] = nil
				instance.operationQueue = instance.operationQueue[:last]
				break
			}
		}
	}
	instance.writeError(
		id,
		"request_cancelled",
		"adapter request was cancelled",
	)
	delete(instance.operationJobs, id)
	instance.operationMu.Unlock()
}

func (instance *server) operationActive(id string) bool {
	instance.operationMu.Lock()
	defer instance.operationMu.Unlock()
	_, active := instance.operationJobs[id]
	return active
}

func (instance *server) operationCount() int {
	instance.operationMu.Lock()
	defer instance.operationMu.Unlock()
	return len(instance.operationJobs)
}
