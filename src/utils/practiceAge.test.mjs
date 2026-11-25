import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatPracticeAge } from './practiceAge.ts';

test('practice age handles relative time boundaries and future timestamps', () => {
  const now = Date.parse('2026-11-19T12:00:00Z');
  for (const [seconds, expected] of [[0, '刚刚'], [59, '刚刚'], [60, '1 分钟前'], [3600, '1 小时前'], [86400, '1 天前'], [2592000, '1 个月前'], [31536000, '1 年前'], [-60, '刚刚']]) {
    assert.equal(formatPracticeAge(new Date(now - seconds * 1000).toISOString(), now), expected);
  }
});
