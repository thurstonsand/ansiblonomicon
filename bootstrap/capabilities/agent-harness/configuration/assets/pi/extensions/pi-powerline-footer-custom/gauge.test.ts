import assert from "node:assert/strict";
import { test } from "node:test";

import { renderGauge } from "./gauge.js";

test("marks approximate gauge values independently from threshold state", () => {
  const percentage = renderGauge(12, false, true);
  const overSoftMax = renderGauge(112, true, true);

  assert.match(percentage, /~12%/);
  assert.match(overSoftMax, /~112!/);
  assert.equal(percentage.length, 23);
  assert.equal(overSoftMax.length, 23);
});
