// Karşıyaka Basketbol – Scriptable widget (iPhone)
// 1) Aşağıdaki GITHUB_KULLANICI ve REPO değerlerini kendinize göre değiştirin.
// 2) Scriptable'da yeni script oluşturup yapıştırın, ana ekrana Scriptable widget'ı ekleyip bu script'i seçin.
const GITHUB_KULLANICI = "KULLANICI_ADINIZ";
const REPO = "karsiyaka-tracker";
const URL_JSON = `https://${GITHUB_KULLANICI}.github.io/${REPO}/data.json`;
const URL_SAYFA = `https://${GITHUB_KULLANICI}.github.io/${REPO}/`;

async function veriAl() {
  const fm = FileManager.local();
  const yol = fm.joinPath(fm.documentsDirectory(), "karsiyaka.json");
  try {
    const d = await new Request(URL_JSON).loadJSON();
    fm.writeString(yol, JSON.stringify(d));
    return d;
  } catch (e) {
    if (fm.fileExists(yol)) return JSON.parse(fm.readString(yol)); // çevrimdışı yedek
    throw e;
  }
}

const gg = (iso) => (iso ? iso.slice(8, 10) + "." + iso.slice(5, 7) : "");
const ALTIN = new Color("#d4a017"), YESIL = new Color("#2e9e5b"), KIRMIZI = new Color("#d64545");

function satir(w, metin, boyut, renk, kalin) {
  const t = w.addText(metin);
  t.font = kalin ? Font.boldSystemFont(boyut) : Font.systemFont(boyut);
  t.textColor = renk || Color.white();
  t.lineLimit = 1;
  return t;
}

async function widgetOlustur() {
  const w = new ListWidget();
  w.backgroundColor = new Color("#15171a");
  w.url = URL_SAYFA;
  w.refreshAfterDate = new Date(Date.now() + 6 * 3600 * 1000);
  try {
    const d = await veriAl();
    satir(w, "KARŞIYAKA BASKET", 11, ALTIN, true);
    w.addSpacer(4);
    satir(w, `${d.rank ?? "-"}. sıra · ${d.wins}G-${d.losses}M`, 18, null, true);
    w.addSpacer(4);
    if (d.last) {
      const k = satir(w, `${d.last.win ? "G" : "M"} ${d.last.pf}-${d.last.pa} ${d.last.opp}`, 12,
        d.last.win ? YESIL : KIRMIZI);
    }
    if (d.next) {
      const ben = d.next.home.includes("Karşıyaka");
      satir(w, `Sıradaki ${gg(d.next.date)}: ${ben ? d.next.away : d.next.home}`, 12, new Color("#9aa0a8"));
    }
    w.addSpacer();
    const f = d.form.map((x) => (x === "G" ? "🟢" : "🔴")).join("");
    satir(w, f, 11);
  } catch (e) {
    satir(w, "Veri alınamadı", 14, KIRMIZI, true);
    satir(w, "URL ayarını kontrol edin", 11);
  }
  return w;
}

const widget = await widgetOlustur();
if (config.runsInWidget) Script.setWidget(widget);
else await widget.presentSmall();
Script.complete();
