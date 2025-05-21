/* src/entrypoints/content.ts
 *  – RRWeb recorder + custom events
 *  – Open+closed Shadow-DOM instrumentation
 *  – Safe for WXT’s Node build (no DOM at top level)
 */

import { defineContentScript } from '#imports'; // <- run `wxt prepare` for TS defs
import * as rrweb from 'rrweb';
import { EventType, IncrementalSource } from '@rrweb/types';

/* ──────────────── globals ──────────────── */
let stopRecording: (() => void) | undefined;
let isRecordingActive = true;

let scrollTimeout: ReturnType<typeof setTimeout> | null = null;
let lastScrollY: number | null = null;
let lastDirection: 'up' | 'down' | null = null;
const DEBOUNCE_MS = 500;

/* ───────────── helper: XPath + CSS selector ───────────── */
function getXPath(el: HTMLElement): string {
  if (el.id) return `id("${el.id}")`;
  if (el === document.body) return el.tagName.toLowerCase();
  let ix = 0;
  for (const sib of Array.from(el.parentNode?.children ?? [])) {
    if (sib === el)
      return `${getXPath(el.parentElement as HTMLElement)}/${el.tagName.toLowerCase()}[${ix + 1}]`;
    if (sib.nodeType === 1 && (sib as HTMLElement).tagName === el.tagName) ix++;
  }
  return el.tagName.toLowerCase();
}

const SAFE_ATTRS = new Set([
  'id','name','type','placeholder','aria-label','aria-labelledby','aria-describedby','role','for',
  'autocomplete','required','readonly','alt','title','src','href','target',
  'data-id','data-qa','data-cy','data-testid',
]);

function cssSelector(el: HTMLElement, xpath: string): string {
  try {
    let sel = el.tagName.toLowerCase();
    el.classList.forEach(c => /^[a-zA-Z_][\w-]*$/.test(c) && (sel += `.${CSS.escape(c)}`));
    for (const { name, value } of Array.from(el.attributes)) {
      if (name === 'class' || !SAFE_ATTRS.has(name)) continue;
      const n = CSS.escape(name);
      sel += value
        ? /["'<>`\s]/.test(value)
          ? `[${n}*="${value.replace(/"/g, '"')}"]`
          : `[${n}="${value}"]`
        : `[${n}]`;
    }
    return sel;
  } catch (e) {
    console.error('selector-gen', e);
    return `${el.tagName.toLowerCase()}[xpath="${xpath.replace(/"/g, '"')}"]`;
  }
}

/* ───────────── Shadow helpers ───────────── */
const composedTarget = (e: Event) =>
  (e.composedPath?.().find(n => n instanceof HTMLElement) ??
    (e.target instanceof HTMLElement ? e.target : null)) as HTMLElement | null;

function chain(el: HTMLElement): string[] {
  const chain: string[] = [];
  let node: HTMLElement | null = el;
  while (node) {
    chain.unshift(cssSelector(node, getXPath(node)));
    node = node.getRootNode() instanceof ShadowRoot ? (node.getRootNode() as ShadowRoot).host as HTMLElement : node.parentElement;
  }
  return chain;
}

function instrumentRoot(root: ShadowRoot) {
  root.addEventListener('click', onClick as EventListener, true);
  root.addEventListener('input', onInput as EventListener, true);
  root.addEventListener('change', onSelect as EventListener, true);
  root.addEventListener('keydown', onKey as EventListener, true);
  root.querySelectorAll('*').forEach(n => n instanceof HTMLElement && n.shadowRoot && instrumentRoot(n.shadowRoot));
}

function scanOpenRoots() {
  document.querySelectorAll('*').forEach(el => {
    const sr = (el as HTMLElement).shadowRoot;
    if (sr) instrumentRoot(sr);
  });
}

function scanClosedRoots() {
  const api = (chrome as any)?.dom?.openOrClosedShadowRoot; // Chrome Canary devtools API
  if (!api) return;
  document.querySelectorAll('*').forEach(el => {
    try {
      const sr = api(el);
      sr && instrumentRoot(sr);
    } catch {}
  });
}

/* ───────────── rrweb recorder ───────────── */
function startRecorder() {
  if (stopRecording) return;
  stopRecording = rrweb.record({
    emit(evt) {
      if (!isRecordingActive) return;

      if (evt.type === EventType.IncrementalSnapshot && evt.data.source === IncrementalSource.Scroll) {
        const d = evt.data as { id: number; x: number; y: number };
        const y = Math.round(d.y), x = Math.round(d.x);
        const dir = lastScrollY != null ? (y > lastScrollY ? 'down' : 'up') : null;
        if (dir && lastDirection && dir !== lastDirection && scrollTimeout) {
          clearTimeout(scrollTimeout);
          scrollTimeout = null;
        }
        lastDirection = dir; lastScrollY = y;
        if (scrollTimeout) clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
          chrome.runtime.sendMessage({ type: 'RRWEB_EVENT', payload: { ...evt, data: { ...d, x, y } } });
          scrollTimeout = null; lastDirection = null;
        }, DEBOUNCE_MS);
      } else {
        chrome.runtime.sendMessage({ type: 'RRWEB_EVENT', payload: evt });
      }
    },
    maskInputOptions: { password: true },
    checkoutEveryNms: 10_000,
    checkoutEveryNth: 200,
  });
  (window as any).rrwebStop = stopRecorder;
  document.addEventListener('click', onClick, true);
  document.addEventListener('input', onInput, true);
  document.addEventListener('change', onSelect, true);
  document.addEventListener('keydown', onKey, true);
}

function stopRecorder() {
  if (!stopRecording) return;
  stopRecording(); stopRecording = undefined; isRecordingActive = false;
  (window as any).rrwebStop = undefined;
  document.removeEventListener('click', onClick, true);
  document.removeEventListener('input', onInput, true);
  document.removeEventListener('change', onSelect, true);
  document.removeEventListener('keydown', onKey, true);
}

/* ───────────── CUSTOM EVENT HANDLERS ───────────── */
function onClick(e: MouseEvent) {
  if (!isRecordingActive) return;
  const el = composedTarget(e);
  if (!el) return;
  chrome.runtime.sendMessage({
    type: 'CUSTOM_CLICK_EVENT',
    payload: {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: getXPath(el),
      cssSelector: chain(el).join(' >> '),
      elementTag: el.tagName,
      elementText: el.textContent?.trim().slice(0, 200) ?? '',
    },
  });
}

function onInput(e: Event) {
  if (!isRecordingActive) return;
  const el = composedTarget(e) as HTMLInputElement | HTMLTextAreaElement;
  if (!el || !('value' in el)) return;
  chrome.runtime.sendMessage({
    type: 'CUSTOM_INPUT_EVENT',
    payload: {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: getXPath(el),
      cssSelector: chain(el).join(' >> '),
      elementTag: el.tagName,
      value: el.type === 'password' ? '********' : el.value,
    },
  });
}

function onSelect(e: Event) {
  if (!isRecordingActive) return;
  const el = composedTarget(e) as HTMLSelectElement;
  if (!el || el.tagName !== 'SELECT') return;
  const opt = el.options[el.selectedIndex];
  chrome.runtime.sendMessage({
    type: 'CUSTOM_SELECT_EVENT',
    payload: {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      xpath: getXPath(el),
      cssSelector: chain(el).join(' >> '),
      elementTag: el.tagName,
      selectedValue: el.value,
      selectedText: opt ? opt.text : '',
    },
  });
}

const KEYS = new Set([
  'Enter','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight',
  'Home','End','PageUp','PageDown','Backspace','Delete',
]);

function onKey(e: KeyboardEvent) {
  if (!isRecordingActive) return;
  let k = '';
  if (KEYS.has(e.key)) k = e.key;
  else if ((e.ctrlKey || e.metaKey) && e.key.length === 1) k = `CmdOrCtrl+${e.key.toUpperCase()}`;
  if (!k) return;

  const el = composedTarget(e);
  chrome.runtime.sendMessage({
    type: 'CUSTOM_KEY_EVENT',
    payload: {
      timestamp: Date.now(),
      url: document.location.href,
      frameUrl: window.location.href,
      key: k,
      xpath: el ? getXPath(el) : '',
      cssSelector: el ? chain(el).join(' >> ') : '',
      elementTag: el ? el.tagName : 'document',
    },
  });
}

/* ───────────── content-script entry ───────────── */
export default defineContentScript({
  matches: ['<all_urls>'],
  runAt: 'document_start',
  main() {
    // Safe patches – run only in the real browser
    if (typeof Element !== 'undefined') {
      const original = Element.prototype.attachShadow;
      Element.prototype.attachShadow = function (init: ShadowRootInit): ShadowRoot {
        if (init && init.mode === 'closed') init = { ...init, mode: 'open' };
        const sr = original.call(this, init);
        instrumentRoot(sr);
        return sr;
      };
    }

    if (typeof customElements !== 'undefined') {
      const origDefine = customElements.define.bind(customElements);
      customElements.define = (name, ctor, opts) => {
        const Wrapped = class extends (ctor as any) {
          constructor(...a: any[]) {
            // @ts-ignore
            super(...a);
            const sr = (this as any).shadowRoot;
            sr && instrumentRoot(sr);
          }
        };
        // @ts-ignore
        return origDefine(name, Wrapped, opts);
      };
    }

    new MutationObserver(recs =>
      recs.forEach(r =>
        r.addedNodes.forEach(n => n instanceof HTMLElement && n.shadowRoot && instrumentRoot(n.shadowRoot)),
      ),
    ).observe(document.documentElement, { childList: true, subtree: true });

    scanOpenRoots();
    scanClosedRoots();

    chrome.runtime.onMessage.addListener(msg => {
      if (msg.type === 'SET_RECORDING_STATUS') msg.payload ? startRecorder() : stopRecorder();
    });

    chrome.runtime.sendMessage({ type: 'REQUEST_RECORDING_STATUS' }, res => {
      if (!chrome.runtime.lastError && res?.isRecordingEnabled) startRecorder();
    });

    window.addEventListener('beforeunload', stopRecorder);
  },
});
