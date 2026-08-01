/** Router hash mínimo */

const routes = new Map();

export function register(path, renderFn) {
  routes.set(path, renderFn);
}

export function navigate(path) {
  if (location.hash.slice(1) === path) {
    // force re-render
    dispatch();
    return;
  }
  location.hash = path;
}

function currentPath() {
  const h = location.hash.slice(1) || '/';
  return h.split('?')[0] || '/';
}

function dispatch() {
  const path = currentPath();
  const fn = routes.get(path) || routes.get('/') || (() => {});
  const app = document.getElementById('app');
  if (app) fn(app);
}

export function start() {
  window.addEventListener('hashchange', dispatch);
  dispatch();
}

export function path() {
  return currentPath();
}
