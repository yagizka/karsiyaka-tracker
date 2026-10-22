# Karşıyaka Basketbol Takip (BSL 2026-27)

Kaynak: https://www.tbf.org.tr/ligler/bsl-2026-2027 → `docs/index.html` (puan durumu, maçlar, istatistik, grafikler).

## Hızlı başlangıç
    python karsiyaka_tracker.py --demo      # sahte veriyle arayüzü gör (docs/index.html)
    python karsiyaka_tracker.py             # gerçek veriyi çek
    python karsiyaka_tracker.py --html sayfa.html   # site engellerse: sayfayı tarayıcıdan kaydet
    python karsiyaka_tracker.py --dump      # bulunan tabloları tables_dump.json'a yaz (hata ayıklama)

## Haftalık otomatik güncelleme
1. Klasörü GitHub'a yükle. 2. Settings → Pages → `docs/` klasörünü yayınla.
3. `.github/workflows/weekly.yml` her Pazartesi çalışır, `docs/` içini günceller.
(Yerelde: cron `0 9 * * 1 python /yol/karsiyaka_tracker.py`; Windows'ta Görev Zamanlayıcı.)

## Önemli
TBF sitesi bot koruması kullanıyor ve yapısını burada test edemedim. İlk çalıştırmada `--dump` ile
tabloları kontrol edin; puan durumu/fikstür ayrı alt sayfalardaysa `URLS` listesine ekleyin.

## iPhone kurulumu (Mac gerekmez)
1. Klasörü GitHub'a yükleyin, Settings → Pages → `docs/` yayınlayın. Actions sekmesinden workflow'u bir kez elle çalıştırın (Run workflow).
2. **Uygulama:** Safari'de `https://KULLANICI.github.io/karsiyaka-tracker/` → Paylaş → Ana Ekrana Ekle.
3. **Widget:** App Store'dan Scriptable'ı kurun, `KarsiyakaWidget.js` içeriğini yeni script'e yapıştırın, ilk iki satırdaki kullanıcı/repo adını düzeltin. Ana ekrana Scriptable widget'ı ekleyip bu script'i seçin.
