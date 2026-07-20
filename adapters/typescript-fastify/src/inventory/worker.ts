import { parentPort, workerData } from "node:worker_threads";

import {
  InventoryProfileError,
  type InventoryRequest,
  buildRun,
} from "./profile.js";

interface InventoryWorkerData {
  request: InventoryRequest;
  key: string;
}

const port = parentPort;
if (port !== null) {
  try {
    const data = workerData as InventoryWorkerData;
    const run = buildRun(data.request, data.key);
    port.postMessage({ kind: "success", run });
  } catch (error: unknown) {
    port.postMessage({
      kind: "failure",
      code: error instanceof InventoryProfileError
        ? error.code
        : "operation_failed",
    });
  }
}
