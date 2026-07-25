"use strict";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message) {
    return false;
  }
  let nativeMessage;
  if (message.type === "open-settings") {
    nativeMessage = { command: "open-settings" };
  } else if (
    message.type === "open-external" &&
    typeof message.url === "string"
  ) {
    nativeMessage = { url: message.url };
  } else {
    return false;
  }
  chrome.runtime.sendNativeMessage(
    "com.outlook_pwa_linux.link_router",
    nativeMessage,
    (response) => {
      if (chrome.runtime.lastError) {
        sendResponse({
          ok: false,
          error: chrome.runtime.lastError.message,
        });
        return;
      }
      sendResponse(response || { ok: false, error: "No native response" });
    },
  );
  return true;
});
