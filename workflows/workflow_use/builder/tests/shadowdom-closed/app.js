/* closed-mode shadow hierarchy */
class InnerClosed extends HTMLElement {
  constructor() {
    super();
    const sr = this.attachShadow({ mode: 'closed' });
    sr.innerHTML = `
      <input id="inner-input" type="text" />
      <button id="inner-btn">Send</button>
    `;
    // put a value in the input so the pytest assertion can verify it
    sr.querySelector('#inner-input').value = 'hello-closed';
  }
}
customElements.define('inner-closed', InnerClosed);

class OuterClosed extends HTMLElement {
  constructor() {
    super();
    const sr = this.attachShadow({ mode: 'closed' });
    sr.innerHTML = `
      <inner-closed></inner-closed>
      <button id="outer-btn">Outer</button>
    `;
  }
}
customElements.define('outer-closed', OuterClosed);

// bootstrap into the DOM
document.getElementById('root').appendChild(new OuterClosed());
