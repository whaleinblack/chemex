import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
Object.defineProperty(window, 'matchMedia', { value: vi.fn().mockImplementation(() => ({
  matches: false, addEventListener() {}, removeEventListener() {},
})) });
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
HTMLElement.prototype.scrollIntoView = () => {};
