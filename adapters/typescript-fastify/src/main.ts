#!/usr/bin/env node

import {
  handleFrame,
  writeTransportError,
} from "./session.js";

const MAX_FRAME_BYTES = 1_048_576;
const decoder = new TextDecoder("utf-8", { fatal: true });
let input = Buffer.alloc(0);
let discardingOversizedFrame = false;

process.stdin.on("data", (chunk: Buffer) => {
  if (discardingOversizedFrame) {
    const delimiter = chunk.indexOf(0x0a);
    if (delimiter < 0) {
      return;
    }
    chunk = chunk.subarray(delimiter + 1);
    discardingOversizedFrame = false;
  }
  input = Buffer.concat([input, chunk]);
  drainFrames();
  if (input.length > MAX_FRAME_BYTES) {
    input = Buffer.alloc(0);
    discardingOversizedFrame = true;
    writeTransportError(
      "frame_too_large",
      `frame exceeds ${MAX_FRAME_BYTES} bytes`,
    );
  }
});

process.stdin.on("end", () => {
  if (input.length > 0) {
    input = Buffer.alloc(0);
    writeTransportError(
      "truncated_frame",
      "frame is not terminated by LF",
    );
  }
});

function drainFrames(): void {
  let delimiter = input.indexOf(0x0a);
  while (delimiter >= 0) {
    const encoded = input.subarray(0, delimiter);
    input = input.subarray(delimiter + 1);
    if (delimiter + 1 > MAX_FRAME_BYTES) {
      writeTransportError(
        "frame_too_large",
        `frame exceeds ${MAX_FRAME_BYTES} bytes`,
      );
    } else if (encoded.length === 0) {
      writeTransportError("invalid_message", "empty protocol frame");
    } else {
      let frame: string;
      try {
        frame = decoder.decode(encoded);
      } catch (error: unknown) {
        if (error instanceof TypeError) {
          writeTransportError("parse_error", "invalid UTF-8 input");
        } else {
          throw error;
        }
        delimiter = input.indexOf(0x0a);
        continue;
      }
      if (handleFrame(frame)) {
        input = Buffer.alloc(0);
        process.stdin.pause();
        return;
      }
    }
    delimiter = input.indexOf(0x0a);
  }
}
