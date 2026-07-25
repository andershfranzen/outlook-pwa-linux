"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");

class FakeStyle {
  constructor() {
    this.cssText = "";
    this.properties = new Map();
  }

  setProperty(name, value, priority = "") {
    this.properties.set(name, { value, priority });
  }
}

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.id = "";
    this.type = "";
    this.title = "";
    this.className = "";
    this.innerHTML = "";
    this.parentElement = null;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.style = new FakeStyle();
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  appendChild(child) {
    return this.insertBefore(child, null);
  }

  insertBefore(child, reference) {
    if (child.parentElement) {
      const oldIndex = child.parentElement.children.indexOf(child);
      child.parentElement.children.splice(oldIndex, 1);
    }
    const index = reference ? this.children.indexOf(reference) : this.children.length;
    assert.notEqual(index, -1);
    this.children.splice(index, 0, child);
    child.parentElement = this;
    return child;
  }

  get nextElementSibling() {
    if (!this.parentElement) {
      return null;
    }
    const index = this.parentElement.children.indexOf(this);
    return this.parentElement.children[index + 1] ?? null;
  }

  closest() {
    return null;
  }

  getBoundingClientRect() {
    if (this.rect) {
      return this.rect;
    }
    const width = Number.parseFloat(
      this.style.cssText.match(/(?:^|;)width:([0-9.]+)px/)?.[1] || "0",
    );
    const height = Number.parseFloat(
      this.style.cssText.match(/(?:^|;)height:([0-9.]+)px/)?.[1] || "0",
    );
    return { x: 0, y: 0, width, height, right: width, bottom: height };
  }

  click() {
    const event = {
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      stopImmediatePropagation() {},
    };
    for (const listener of this.listeners.get("click") ?? []) {
      listener(event);
    }
    return event;
  }
}

const root = new FakeElement("html");
const head = new FakeElement("head");
const toolbarHost = new FakeElement("div");
const toolbar = new FakeElement("div");
toolbar.id = "headerButtonsRegionId";
toolbarHost.rect = { x: 0, y: 0, width: 164, height: 48, right: 164, bottom: 48 };
const officialSettings = new FakeElement("button");
officialSettings.id = "O365_SettingsButton";
officialSettings.className = "outlook-private-positioning-class";
officialSettings.setAttribute("aria-label", "Settings");
toolbar.appendChild(officialSettings);
root.appendChild(head);
toolbarHost.appendChild(toolbar);
root.appendChild(toolbarHost);

function findById(element, id) {
  if (element.id === id) {
    return element;
  }
  for (const child of element.children) {
    const match = findById(child, id);
    if (match) {
      return match;
    }
  }
  return null;
}

const documentListeners = new Map();
global.document = {
  title: "Mail - Outlook",
  documentElement: root,
  head,
  querySelector(selector) {
    if (selector.includes("#O365_SettingsButton")) {
      return officialSettings;
    }
    if (selector === 'meta[name="theme-color"]') {
      return null;
    }
    return null;
  },
  querySelectorAll() {
    return [];
  },
  getElementById(id) {
    return findById(root, id);
  },
  createElement(tagName) {
    return new FakeElement(tagName);
  },
  addEventListener(type, listener) {
    documentListeners.set(type, listener);
  },
};
global.Element = FakeElement;
global.getComputedStyle = (element) => ({
  color: "rgb(255, 255, 255)",
  flexBasis: element === toolbarHost ? "164px" : "auto",
});

let observerCallback;
global.MutationObserver = class {
  constructor(callback) {
    observerCallback = callback;
  }

  observe() {}
};

const runtimeMessages = [];
global.chrome = {
  runtime: {
    getURL: (resource) => `extension://${resource}`,
    sendMessage: (message) => runtimeMessages.push(message),
  },
};
global.fetch = async () => ({
  json: async () => ({
    themeColor: "#0f6cbd",
    routeExternalLinks: false,
    internalDomains: [],
  }),
});

let officialClicks = 0;
officialSettings.addEventListener("click", () => {
  officialClicks += 1;
});

require(path.join(__dirname, "..", "extension", "content.js"));

async function main() {
  await new Promise((resolve) => setTimeout(resolve, 150));

  const wrapperSettings = document.getElementById("outlook-pwa-linux-settings");
  assert.ok(wrapperSettings);
  assert.deepEqual(toolbar.children, [wrapperSettings, officialSettings]);
  assert.equal(wrapperSettings.nextElementSibling, officialSettings);
  assert.equal(officialSettings.className, "outlook-private-positioning-class");
  assert.equal(wrapperSettings.className, "outlook-pwa-linux-control");
  assert.notEqual(wrapperSettings.className, officialSettings.className);
  assert.match(wrapperSettings.style.cssText, /flex:0 0 48px/);
  assert.match(wrapperSettings.style.cssText, /position:relative/);
  assert.deepEqual(toolbarHost.style.properties.get("flex"), {
    value: "0 2 212px",
    priority: "important",
  });
  assert.deepEqual(toolbarHost.style.properties.get("min-width"), {
    value: "212px",
    priority: "important",
  });
  assert.equal(
    wrapperSettings.getAttribute("aria-label"),
    "Outlook for Linux settings",
  );

  const wrapperEvent = wrapperSettings.click();
  assert.equal(wrapperEvent.defaultPrevented, true);
  assert.deepEqual(runtimeMessages, [{ type: "open-settings" }]);
  assert.equal(officialClicks, 0);

  officialSettings.click();
  assert.equal(officialClicks, 1);
  assert.deepEqual(runtimeMessages, [{ type: "open-settings" }]);

  toolbar.insertBefore(officialSettings, wrapperSettings);
  observerCallback();
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.deepEqual(toolbar.children, [wrapperSettings, officialSettings]);
  assert.equal(
    toolbar.children.filter(
      (element) => element.id === "outlook-pwa-linux-settings",
    ).length,
    1,
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
