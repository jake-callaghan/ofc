import test from 'node:test';
import assert from 'node:assert/strict';
import { runningTime } from '../src/lib/tableTime.js';

test('table age handles minute, hour, day and future-clock boundaries', () => {
  const created = 1000;
  const atMinutes = (minutes) =>
    runningTime(created, created * 1000 + minutes * 60000);
  assert.equal(atMinutes(-1), '<1m');
  assert.equal(atMinutes(0), '<1m');
  assert.equal(atMinutes(59), '59m');
  assert.equal(atMinutes(60), '1h 0m');
  assert.equal(atMinutes(1439), '23h 59m');
  assert.equal(atMinutes(1440), '1d 0h');
});
