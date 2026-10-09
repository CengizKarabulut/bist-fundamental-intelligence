# Changelog

## 1.1.0-rc1 — 2026-10-10 (RELEASE CANDIDATE; doğrulama bekleniyor)

- Pusula ve tüm BIST denetiminde saptanan tarih/ana ortaklık özkaynak
  problemlerine yönelik satır kökeni ve ayrı mutabakat kayıtları.
- Çoklu pay sınıfı seçimi için ISCTR / KRDMD tercihli benchmark eşleşmesi
  ve aşırı çarpan koruması.
- TTM FAVÖK: açık finansal tablo satırından veya birbirini izleyen dört
  çeyrekteki faaliyet sonucu + amortisman kalemlerinden yeniden hesaplama.
  Yeniden hesaplanan sonuç yaklaşık olarak etiketlenir; bankalar/GYO/holding
  gibi profillerde uygulanmaz.
- FD/FAVÖK yalnız aynı finansal dönem bilanço borç/nakit/yatırım kalemleri
  ile ve geçerli FAVÖK verisi varsa üretilir. Veri yetersizse N/A.
- Bağımsız F/K, PD/DD, FD/FAVÖK kapsaması ve FAVÖK kaynağı birleşik audit
  raporuna eklenir; kalite kapısı F/K ve PD/DD kapsam düşüşlerini yakalar.
- Testler: çeyrek sürekliliği, gerçek FAVÖK tercih sırası, yaklaşık hesap,
  eksik dönem, uygunsuz şirket tipi, eksik net borç.
- **#79 sonucu bu sürümün sonucu DEĞİLDİR.** v1.1.0-rc1,
  yeni Regression Smoke Test ve Full BIST Audit sonucuna kadar Stable değildir.


## Geliştirme aşaması — 2026-10-09 (henüz release değil)

### Full BIST Audit #79 doğrulaması (9 Ekim 2026, 19:14)

- 621/621 benzersiz şirket; XU100 100/100, ERROR 0, CRITICAL 0.
- WARNING 160, INFO 221, OK 240; önceki #74 raporunda WARNING 141. Yeni PB_BASIS_RECONCILIATION_REQUIRED uyarısı 24 şirket, bunların 19'u önceki audit'te WARNING değildi.
- Bağımsız hesaplanan F/K 290 şirket, PD/DD 592 şirket, FD/FAVÖK 0 şirket; hesaplama kapsaması sürmektedir.
- İki audit arasında temsilci pay sınıfı ISBTR → ISCTR değişti. ISBTR'nin önceki bağımsız PD/DD'si yaklaşık 658185x iken ISCTR yaklaşık 0,76x çıktı. Çoklu pay sınıfları için kararlı seçim gereklidir.
- #79 SONRASI DÜZELTME: ISCTR ve KRDMD şirket karşılaştırmasında tercihli temsilci pay sınıfı olarak seçilecek; veri yoksa normal seçim kullanılacak.
- #79 SONRASI DÜZELTME: bağımsız hesaplanan F/K, PD/DD ve FD/FAVÖK olağan dışı büyüklükleri ayrıca WARNING üretir; muhasebe hatası hükmü değildir.
- Tercihli pay sınıfı ve uç çarpan için regresyon testleri eklendi; sonraki full-market çalışmanın sonucu **henüz doğrulanmadı**.



### Full BIST Audit #74 doğrulaması (kullanıcı artifact'ı)

- 621/621 şirket, XU100 100/100; ERROR 0, CRITICAL 0, WARNING 141, INFO 228, OK 252.
- Bağımsız P/B kapsamı 592 şirkete çıktı (önceki audit: 0); bağımsız P/E: 289, FD/FAVÖK: 0.
- 17 şirkette kaynak PD/DD'den ters hesaplanan özkaynak ile bilanço ana ortaklık özkaynağı >%10 farklı; 15 şirkette sağlayıcı tarihsel finansalları eksik.
- Önceki BIST audit ile karşılaştırmada 7 ortak hissenin statüsü değişti; pay sınıfı evreni KRDMB yerine KRDMA olarak değişti.
- Sonraki iki düzeltme: P/B < 1 için mutabakat farkının 1 tabanlı paydayla maskelenmesi kaldırıldı, >%10 özkaynak baz farkı WARNING ile incelemeye taşındı.
- **Bu sonraki kod değişikliklerinin tam audit test sonuçları henüz burada doğrulanmadı.**


- Finansal tablo bazlı F/K ve PD/DD mutabakatı için bağımsız hesaplama modülü eklendi. Ana ortaklık kalemleri açıkça tespit edilemiyorsa oran hesaplanmaz.
- FD/FAVÖK için gerçek TTM FAVÖK doğrulanmadan sayı üretilmez.
- BIST audit CSV çıktısına hesaplanan oranlar, kaynak karşılaştırmaları ve finansal satır adları eklendi.
- TTM hesaplarında ardışık çeyrek zorunluluğu, eksik net borç bileşenlerinin sıfır sayılmaması, ROE/ROA için ortalama bilanço koruması eklendi.
- Audit çıktılarına geçici hazırlık durumu ve açıklama eklendi.
- Bu değişiklikler henüz yeni bir 621 şirketlik audit başarı raporu ile doğrulanmadı. v1.0.2 için önceki test sonuçları yeni kod için kanıt sayılamaz.


## 1.0.2 — 2026-10-09

Son profesyonel inceleme yaması.

- Banka dışı finansal şirketlerde XI_29 şablonundaki tamamen sıfır finans-sektörü satırları veri olarak kabul edilmez.
- GLBMD benzeri broker/menkul değer şirketlerinde gerçek faaliyet sonucu ve ticari/faaliyet alacaklarına kontrollü fallback uygulanır.
- Özel finansal motor raporu kullanılan satırın gerçek ekonomik adını gösterir.
- Bankalarda özkaynak/aktif oranının BDDK sermaye yeterlilik oranı (SYR) olmadığı açıkça belirtilir.
- Yeni fallback davranışı regresyon testine kilitlenmiştir.


## 1.0.1 — 2026-10-09

Kararlı sürüm son profesyonel audit düzeltmesi.

- KAP'ta **Holdingler ve Yatırım Şirketleri** olarak sınıflanan ancak XHOLD endeks üyeliği üzerinden yakalanamayan ATSYH, ISBIR ve KERVN için holding profili düzeltildi.
- Bu şirketlerde generic sanayi kalite/değerleme skoru yerine Holding/NAD metodolojisi zorunlu hale getirildi.
- Profil regresyon kontrolleri bu üç edge-case'i kalıcı olarak kapsıyor.
- Sigorta özkaynak/aktif oranı artık solvency/sermaye yeterliliği gibi yorumlanmıyor; yalnız bilanço bilgisi olarak gösteriliyor.
- Tarihsel mali tablo sağlayıcıda bulunmayan şirketlerde skorun güncel çapraz-kesit veriye dayandığı açıkça belirtiliyor.


## 1.0.0 — 2026-10-09

İlk tam BIST kararlı sürümü.

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
