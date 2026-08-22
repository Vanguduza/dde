import { contextBridge, ipcRenderer } from "electron";

export type DesktopApi = {
  navigate: (nav: string) => Promise<void>;
  postMessage: (msg: Record<string, unknown>) => Promise<void>;
  openExternal: (url: string) => Promise<void>;
};

const api: DesktopApi = {
  navigate: (nav) => ipcRenderer.invoke("dde:navigate", nav),
  postMessage: (msg) => ipcRenderer.invoke("dde:message", msg),
  openExternal: (url) => ipcRenderer.invoke("dde:openExternal", url),
};

contextBridge.exposeInMainWorld("ddeDesktop", api);
