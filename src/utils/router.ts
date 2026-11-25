import { useSyncExternalStore } from 'react';

export type PageRoute =
  | { view: 'books' }
  | { view: 'report' }
  | { view: 'practice'; bookId: string }
  | { view: 'admin'; bookId: string; chapterId: string };

export function parseRoute(hash: string): PageRoute {
  try {
    const parts = hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent);
    if (parts[0] === 'report' && parts.length === 1) return { view: 'report' };
    if (parts[0] === 'practice' && parts.length === 2 && parts[1]) {
      return { view: 'practice', bookId: parts[1] };
    }
    if (parts[0] === 'admin' && parts.length <= 3) {
      return { view: 'admin', bookId: parts[1] || '', chapterId: parts[2] || '' };
    }
  } catch { /* Malformed URLs fall back to the library. */ }
  return { view: 'books' };
}

export function navigateRoute(path: string, replace = false) {
  const hash = `#${path}`;
  if (window.location.hash === hash) return;
  if (replace) {
    window.history.replaceState(null, '', hash);
    window.dispatchEvent(new Event('hashchange'));
  } else {
    window.location.hash = path;
  }
}

const subscribe = (listener: () => void) => {
  window.addEventListener('hashchange', listener);
  return () => window.removeEventListener('hashchange', listener);
};
export function usePageHash() {
  return useSyncExternalStore(subscribe, () => window.location.hash, () => '');
}
