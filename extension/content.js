"use strict";

let integrationConfig = {
  themeColor: "",
  routeExternalLinks: false,
  internalDomains: [],
};
let updateStatus = null;
let updateCheckInFlight = false;

function hostMatches(hostname, domain) {
  const normalizedHost = hostname.toLowerCase();
  const normalizedDomain = domain.toLowerCase();
  return (
    normalizedHost === normalizedDomain ||
    normalizedHost.endsWith(`.${normalizedDomain}`)
  );
}

function isInternal(url) {
  return integrationConfig.internalDomains.some((domain) =>
    hostMatches(url.hostname, domain),
  );
}

function applyThemeColor() {
  if (!integrationConfig.themeColor) {
    return;
  }
  let theme = document.querySelector('meta[name="theme-color"]');
  if (!theme) {
    theme = document.createElement("meta");
    theme.name = "theme-color";
    (document.head || document.documentElement).appendChild(theme);
  }
  theme.content = integrationConfig.themeColor;
}

function normalizeOutlookTitle() {
  if (document.title.includes("(PWA)")) {
    document.title = document.title.replace(/\s*\(PWA\)\s*/gi, " ").trim();
  }
}

function settingsControlCandidate() {
  const direct = document.querySelector(
    [
      "#O365_SettingsButton",
      "#owaSettingsBtn_container",
      "#SettingsIcon",
      "button[data-automation-id='settingsButton']",
      "button[aria-label='Settings']",
      "button[title='Settings']",
    ].join(","),
  );
  if (direct) {
    return direct;
  }
  return [...document.querySelectorAll("button,[role='button']")].find(
    (element) => {
      if (element.id === "outlook-pwa-linux-settings") {
        return false;
      }
      const label = (
        element.getAttribute("aria-label") ||
        element.getAttribute("title") ||
        ""
      ).trim();
      return /^settings(?:$|[,.])/i.test(label);
    },
  );
}

function styleSettingsControl(button, outlookSettings) {
  button.className = "outlook-pwa-linux-control";
  button.style.cssText = [
    "align-items:center",
    "appearance:none",
    "background:transparent",
    "border:0",
    "border-radius:2px",
    "box-sizing:border-box",
    "color:inherit",
    "cursor:pointer",
    "display:inline-flex",
    "flex:0 0 48px",
    "height:48px",
    "inset:auto",
    "isolation:isolate",
    "justify-content:center",
    "line-height:0",
    "margin:0",
    "min-width:48px",
    "padding:5px",
    "pointer-events:auto",
    "position:relative",
    "width:48px",
    "z-index:auto",
  ].join(";");
  button.style.setProperty(
    "color",
    getComputedStyle(outlookSettings).color,
    "important",
  );
}

function applyUpdateIndicator(button) {
  const badge = document.getElementById("outlook-pwa-linux-update-badge");
  const available =
    updateStatus?.ok === true && updateStatus.updateAvailable === true;
  if (badge) {
    badge.style.display = available ? "block" : "none";
  }
  const description = available
    ? `Outlook for Linux settings — update ${updateStatus.latestVersion} available`
    : "Outlook for Linux settings";
  button.setAttribute("aria-label", description);
  button.title = description;
}

function reserveSettingsControlSpace(button, outlookSettings) {
  const region = outlookSettings.parentElement;
  const host = region?.parentElement;
  if (region?.id !== "headerButtonsRegionId" || !host) {
    return;
  }

  const baseWidthAttribute = "data-outlook-pwa-base-width";
  let baseWidth = Number.parseFloat(host.getAttribute(baseWidthAttribute) || "");
  if (!Number.isFinite(baseWidth)) {
    const computedBasis = Number.parseFloat(getComputedStyle(host).flexBasis);
    baseWidth = Math.max(
      host.getBoundingClientRect().width,
      Number.isFinite(computedBasis) ? computedBasis : 0,
    );
    host.setAttribute(baseWidthAttribute, String(baseWidth));
  }

  const controlWidth = button.getBoundingClientRect().width || 48;
  const requiredWidth = Math.ceil(baseWidth + controlWidth);
  host.style.setProperty("flex", `0 2 ${requiredWidth}px`, "important");
  host.style.setProperty("min-width", `${requiredWidth}px`, "important");
  host.style.setProperty("width", `${requiredWidth}px`, "important");
}

function installSettingsControl() {
  const outlookSettings = settingsControlCandidate();
  if (!outlookSettings?.parentElement) {
    return;
  }
  const existing = document.getElementById("outlook-pwa-linux-settings");
  if (existing) {
    styleSettingsControl(existing, outlookSettings);
    applyUpdateIndicator(existing);
    if (
      existing.parentElement !== outlookSettings.parentElement ||
      existing.nextElementSibling !== outlookSettings
    ) {
      outlookSettings.parentElement.insertBefore(existing, outlookSettings);
    }
    reserveSettingsControlSpace(existing, outlookSettings);
    return;
  }
  const button = document.createElement("button");
  button.id = "outlook-pwa-linux-settings";
  button.type = "button";
  button.setAttribute("aria-label", "Outlook for Linux settings");
  button.setAttribute("data-outlook-pwa-control", "wrapper-settings");
  button.title = "Outlook for Linux settings";
  styleSettingsControl(button, outlookSettings);
  const brandIcon = document.createElement("img");
  brandIcon.src = chrome.runtime.getURL("a5-settings.svg");
  brandIcon.alt = "";
  brandIcon.setAttribute("aria-hidden", "true");
  brandIcon.setAttribute("draggable", "false");
  brandIcon.style.cssText = [
    "display:block",
    "height:24px",
    "pointer-events:none",
    "user-select:none",
    "width:24px",
  ].join(";");
  button.appendChild(brandIcon);
  const badge = document.createElement("span");
  badge.id = "outlook-pwa-linux-update-badge";
  badge.setAttribute("aria-hidden", "true");
  badge.style.cssText = [
    "background:#d83b01",
    "border:2px solid currentColor",
    "border-radius:50%",
    "display:none",
    "height:8px",
    "position:absolute",
    "right:7px",
    "top:7px",
    "width:8px",
  ].join(";");
  button.appendChild(badge);
  button.addEventListener("mouseenter", () => {
    button.style.background = "rgba(255,255,255,.14)";
  });
  button.addEventListener("mouseleave", () => {
    button.style.background = "transparent";
  });
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    chrome.runtime.sendMessage({ type: "open-settings" });
  });
  outlookSettings.parentElement.insertBefore(button, outlookSettings);
  applyUpdateIndicator(button);
  reserveSettingsControlSpace(button, outlookSettings);
}

function requestUpdateStatus() {
  if (updateCheckInFlight) {
    return;
  }
  updateCheckInFlight = true;
  chrome.runtime.sendMessage({ type: "check-update" }, (response) => {
    updateCheckInFlight = false;
    if (chrome.runtime.lastError || !response) {
      return;
    }
    updateStatus = response;
    const button = document.getElementById("outlook-pwa-linux-settings");
    if (button) {
      applyUpdateIndicator(button);
    }
  });
}

let settingsControlTimer;
function scheduleSettingsControl() {
  clearTimeout(settingsControlTimer);
  settingsControlTimer = setTimeout(() => {
    normalizeOutlookTitle();
    installSettingsControl();
  }, 100);
}

async function loadConfiguration() {
  try {
    const response = await fetch(chrome.runtime.getURL("config.json"), {
      cache: "no-store",
    });
    integrationConfig = await response.json();
  } catch (_error) {
    return;
  }
  applyThemeColor();
  normalizeOutlookTitle();
  if (!document.head) {
    document.addEventListener("DOMContentLoaded", applyThemeColor, {
      once: true,
    });
  }
  scheduleSettingsControl();
  requestUpdateStatus();
}

document.addEventListener(
  "click",
  (event) => {
    if (!integrationConfig.routeExternalLinks || event.defaultPrevented) {
      return;
    }
    const origin =
      event.target instanceof Element ? event.target : event.target?.parentElement;
    const link = origin?.closest("a[href]");
    if (!link || link.hasAttribute("download")) {
      return;
    }
    let target;
    try {
      target = new URL(link.href, document.baseURI);
    } catch (_error) {
      return;
    }
    if (
      !["http:", "https:"].includes(target.protocol) ||
      isInternal(target)
    ) {
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    chrome.runtime.sendMessage({
      type: "open-external",
      url: target.href,
    });
  },
  true,
);

void loadConfiguration();

if (typeof window !== "undefined") {
  window.setInterval(requestUpdateStatus, 60 * 60 * 1000);
}

const settingsControlObserver = new MutationObserver(scheduleSettingsControl);
settingsControlObserver.observe(document.documentElement, {
  childList: true,
  subtree: true,
});
