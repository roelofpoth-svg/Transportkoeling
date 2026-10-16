// Instellingen van de selectietool. Pas hier de webshoplink aan; {artnr} wordt vervangen door het artikelnummer.
window.TK_CONFIG = {
  webshopUrl: 'https://wijlhuizenconnects.com/nl/search?q={artnr}',
  webshopLabel: 'Bekijk in webshop',
  // Link openen in nieuw tabblad (aan te raden wanneer de tool in een iframe staat)
  webshopNewTab: true,
  // Foto-zoeker (binnendienst): adres van de eigen server (Cloudflare Worker), zie README. Leeg = uit.
  fotoZoekerApi: 'https://wijlhuizen-chatbot.roelofpoth.workers.dev',
  // Het chat-rondje rechtsonder tonen. false = verbergen (dan alleen te openen via #/foto).
  fotoZoekerTonen: true,
};
