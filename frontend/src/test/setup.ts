import '@testing-library/jest-dom/vitest'

// jsdom does not implement the dialog element's methods. Real browsers do, and
// that behaviour - focus trapping, inertness, Escape-to-close - is precisely
// why `Modal` uses a native <dialog>. Stub just enough for the open/close state
// to be observable in tests.
if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
}
