const FAVICON = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">',
  '<path d="M2 14c3-7 7-7 11-2s7 5 9-2" fill="none" stroke="#ff69b4" ',
  'stroke-width="4" stroke-linecap="round"/></svg>',
].join("");

export function installFavicon(): void {
  const favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = `data:image/svg+xml,${encodeURIComponent(FAVICON)}`;
  document.head.querySelector('link[rel="icon"]')?.remove();
  document.head.append(favicon);
}
