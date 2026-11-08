ObjC.import("Foundation");

function readLimit(client) {
  const error = Ref();
  const limit = client.getMCLLimitWithError(error);
  if (!error[0].isNil()) {
    throw new Error(ObjC.unwrap(error[0].localizedDescription));
  }
  return limit;
}

function run(argv) {
  if (argv.length > 1) {
    throw new Error("usage: charge_limit.js [80|85|90|95|100]");
  }
  // PowerUI is private, but changes the native setting without SMC writes or a daemon.
  if (
    !$.NSBundle.bundleWithPath(
      "/System/Library/PrivateFrameworks/PowerUI.framework",
    ).load
  ) {
    throw new Error("Could not load PowerUI");
  }
  const client = $.NSClassFromString(
    "PowerUISmartChargeClient",
  ).alloc.initWithClientName("ansiblonomicon");
  if (!client.isMCLSupported) {
    throw new Error("Native battery charge limits are not supported");
  }
  if (argv.length === 0) {
    return readLimit(client);
  }
  const desired = Number(argv[0]);
  if (![80, 85, 90, 95, 100].includes(desired)) {
    throw new Error("Charge limit must be 80, 85, 90, 95, or 100");
  }
  const error = Ref();
  if (!client.setMCLLimitError(desired, error)) {
    throw new Error(
      error[0].isNil()
        ? "PowerUI refused the charge limit"
        : ObjC.unwrap(error[0].localizedDescription),
    );
  }
  const actual = readLimit(client);
  if (actual !== desired) {
    throw new Error(`Charge limit is ${actual}, expected ${desired}`);
  }
  return actual;
}
