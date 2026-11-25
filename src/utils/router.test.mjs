import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRoute, navigateRoute } from './router.ts';

test('deep links restore library, practice and nested admin locations', () => {
  assert.deepEqual(parseRoute(''), { view: 'books' });
  assert.deepEqual(parseRoute('#/'), { view: 'books' });
  assert.deepEqual(parseRoute('#/report'), { view: 'report' });
  assert.deepEqual(parseRoute('#/practice/book%2F1'), { view: 'practice', bookId: 'book/1' });
  assert.deepEqual(parseRoute('#/admin'), { view: 'admin', bookId: '', chapterId: '' });
  assert.deepEqual(parseRoute('#/admin/book/chapter%20one'), { view: 'admin', bookId: 'book', chapterId: 'chapter one' });
});

test('invalid and malformed links safely return to the library', () => {
  for (const hash of ['#/report/extra', '#/missing', '#/practice', '#/practice/', '#/practice/a/extra', '#/practice/%XX', '#/admin/a/b/extra']) {
    assert.deepEqual(parseRoute(hash), { view: 'books' });
  }
});

test('navigation adds history while redirects replace the current entry and notify subscribers', () => {
  const calls = [];
  globalThis.window = {
    location: { hash: '#/' },
    history: { replaceState: (...args) => calls.push(args) },
    dispatchEvent: event => calls.push(event.type),
  };
  try {
    navigateRoute('/practice/book');
    assert.equal(window.location.hash, '/practice/book');
    navigateRoute('/', true);
    assert.deepEqual(calls, [[null, '', '#/'], 'hashchange']);
  } finally { delete globalThis.window; }
});
