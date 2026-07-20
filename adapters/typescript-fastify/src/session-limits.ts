export const DEFAULT_MAX_PENDING = 64;
export const DEFAULT_MAX_REQUESTS = 65_536;

export class SessionLimits {
  private acceptedRequests = 0;

  public constructor(
    public readonly maxPending = DEFAULT_MAX_PENDING,
    public readonly maxRequests = DEFAULT_MAX_REQUESTS,
  ) {
    if (
      !Number.isSafeInteger(maxPending)
      || maxPending < 1
      || maxPending > DEFAULT_MAX_PENDING
      || !Number.isSafeInteger(maxRequests)
      || maxRequests < 2
      || maxRequests > DEFAULT_MAX_REQUESTS
    ) {
      throw new RangeError(
        "session limits must be exact integers within protocol maxima",
      );
    }
  }

  public acceptRequest(method: string): boolean {
    if (
      this.acceptedRequests >= this.maxRequests
      || (
        this.acceptedRequests === this.maxRequests - 1
        && method !== "ucf.shutdown"
      )
    ) {
      return false;
    }
    this.acceptedRequests += 1;
    return true;
  }

  public acceptsPending(currentPending: number): boolean {
    return currentPending < this.maxPending;
  }
}
