class InnerElement extends HTMLElement {
  constructor() {
    super();
    const sr = this.attachShadow({ mode: 'open' });
    sr.innerHTML = `
      <input id="inner-input" type="text" />
      <button id="inner-btn">Send</button>
    `;
  }
}
customElements.define('inner-element', InnerElement);

class OuterElement extends HTMLElement {
  constructor() {
    super();
    const sr = this.attachShadow({ mode: 'open' });
    sr.innerHTML = `
      <inner-element></inner-element>
      <button id="outer-btn">Outer</button>
    `;
  }
}
customElements.define('outer-element', OuterElement);

document.getElementById('__next').appendChild(new OuterElement());