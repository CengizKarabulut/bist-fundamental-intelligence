# Changelog

## 1.0.0 — 2026-10-09

İlk tam BIST sürüm adayı.

### Analiz motoru
- Güncel BIST şirket evreni dinamik olarak alınır ve şirket bazında tekilleştirilir.
- Hedef şirket; endüstri, sektör, BIST100 ve tüm BIST dağılımlarıyla karşılaştırılır.
- İş Yatırım hedef-şirket finansallarında ve desteklenen gerçekleşen oranlarda birincil veri katmanıdır.
- TradingView Screener geniş BIST çapraz-kesit ve benchmark katmanıdır.
- BorsaPy endeks bileşenleri, KAP/İş Yatırım erişimi ve tarihsel finansallar için kullanılır.
- Kaynak farkları gizlenmez; ayrı doğrulama ve veri güven katmanında raporlanır.
- Negatif/sıfır F/K, PD/DD, FD/FAVÖK ve Fiyat/FCF ekonomik olarak anlamsız kabul edilerek ucuzluk skoru üretmez.

### Tarihsel finansallar
- Hedef şirkette 12 çeyrek finansal analiz.
- Uygun olduğunda 5 yıllık yıllık finansal özgeçmiş.
- TTM ciro/net kâr büyümesi, marjlar, CFO, FCF, nakit dönüşümü, bilanço ve özkaynak/aktif trendleri.
- Şirketin kendi yıllık net marj, yaklaşık ROE ve yaklaşık ROA geçmişi.
- TMS 29 / yeniden ifade / kaynak güncelleme farkları veri doğrulama katmanında görünür tutulur.

### Özel profil motorları
- Banka ve katılım bankası.
- Sigorta.
- Banka dışı finansal kuruluş.
- GYO.
- Holding.
- Yatırım ortaklığı.
- GYO/Holding/Yatırım Ortaklığı için gerçek NAD verisi yoksa değerleme uydurulmaz; rapor VALUATION_PARTIAL olur.

### Kalite güvence
- Temsili regresyon seti: ASELS, AKBNK, ALBRK, EKGYO, KCHOL, AGESA, GLBMD, ISFIN.
- Full BIST Audit: 8 paralel shard ile bütün güncel BIST şirketleri.
- Release Quality Gate: herhangi bir ERROR/CRITICAL, yetersiz BIST evreni veya eksik XU100 kapsamı oluşursa CI başarısız olur.
- Son doğrulanmış tam audit: 621 benzersiz şirket, XU100 100/100, ERROR 0, CRITICAL 0.

### Bilinen veri sınırları
- Bazı şirketlerde sağlayıcılar tarihsel mali tablo sağlamayabilir; bu durum motor hatasından ayrı tutulur.
- GYO/Holding gerçek NAD için güvenilir harici NAV girdisi gerekebilir.
- Sağlayıcılar arasında oran tanımı, raporlama tarihi ve TMS 29 bazları farklı olabilir.
