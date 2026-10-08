# BIST Fundamental Intelligence

BIST Fundamental Intelligence v1.0; bir BIST sembolünü alıp güncel piyasa/temel verileri, tarihsel mali tabloları, sektör/endüstri dağılımlarını, BIST100 karşılaştırmasını ve şirket tipine özel finansal kuralları tek bir profesyonel HTML/JSON raporunda birleştiren araştırma motorudur.

Amaç tek bir AL/SAT puanı üretmek değildir. Şirket kalitesi, büyüme, kârlılık, finansal sağlık, nakit kalitesi, değerleme ve göreli konum ayrı tutulur.

## Kullanım

GitHub üzerinde Actions → Hisse Analizi → Run workflow yolunu açın ve symbol alanına örneğin ASELS, AKBNK, EKGYO veya KCHOL yazın. Çalışma bittiğinde bist-report-SEMBOL artifact'ını indirin ve SEMBOL_report.html dosyasını açın.

Yerel kullanım:

    pip install -r requirements.txt
    python analyze.py ASELS

Windows'ta HISSE_ANALIZ.bat da kullanılabilir.

## Veri otoritesi

Motor farklı kaynakları kör biçimde ortalamaz.

- İş Yatırım / BorsaPy mali tabloları: hedef şirketin tarihsel bilanço, gelir tablosu ve uygun profillerde nakit akışı için ana kaynaktır.
- İş Yatırım gerçekleşen şirket oranları: hedef hissede F/K, PD/DD, FD/FAVÖK, ROE ve ROA bulunabildiğinde önceliklidir.
- Mali tablodan yeniden hesaplanan TTM metrikleri: ciro/net kâr büyümesi, marjlar, FCF marjı, cari oran ve özkaynak/aktif gibi alanlarda hedef şirket için önceliklidir.
- TradingView Screener: tüm BIST üzerindeki hızlı çapraz-kesit dağılımı, sektör/endüstri medyanı ve yüzdelik sıralamalar için kullanılır.
- BorsaPy Index: XU100 ve uygun sektör endeksi bileşenleri/performansı için önceliklidir.
- Kaynaklar ayrışırsa fark gizlenmez; doğrulama tablosunda görünür ve veri güven puanına yansır.

Eksik veri sıfır kabul edilmez.

## Karşılaştırma evrenleri

Sabit 5-10 emsal listesi kullanılmaz. Her çalışmada güncel evren üzerinden aynı endüstri, aynı sektör, güncel BIST100 ve veri bulunan tüm BIST medyanları ile yüzdelik/göreli konumları hesaplanır. Bir şirketin farklı pay sınıflarının dağılımı yapay biçimde bozmaması için şirket bazlı tekilleştirme uygulanır.

## Ana finansal katmanlar

Normal sanayi/operasyonel şirketlerde veri bulunabildiği ölçüde şu aileler kullanılır:

- Değerleme: F/K, PD/DD, FD/FAVÖK, Fiyat/FCF
- Kârlılık: ROE, ROA, ROIC, brüt/faaliyet/net/FAVÖK marjları
- Büyüme: ciro, EPS, net kâr, 3Y CAGR
- Finansal sağlık: cari oran, likidite, borç/özsermaye, net borç/FAVÖK, özsermaye/aktif
- Nakit kalitesi: faaliyet nakit akışı, FCF, CFO/net kâr, FCF marjı, Piotroski
- Relatif fiyat: XU100 ve uygun sektör endeksine karşı 3A/6A/12A performans

Negatif veya sıfır F/K, PD/DD, FD/FAVÖK ve Fiyat/FCF ucuz sayılmaz; ekonomik olarak anlamsızsa skor dışı bırakılır.

## 12 çeyrek ve yıllık özgeçmiş

Hedef şirket için son 12 çeyrek finansallar, uygun olduğunda 5 yıllık yıllık finansallar, yıllık ciro/net kâr CAGR, marj yönü, özkaynak/aktif gelişimi, borç ve nakit trendi, kârın nakde dönüşümü ve şirketin kendi yıllık net marj / yaklaşık ROE / yaklaşık ROA eğilimi raporlanır.

Tarihsel ROE/ROA tablosunda dönem sonu özkaynak/aktif kullanıldığı için bu bölüm yaklaşık özgeçmiş karşılaştırmasıdır; ana sektör skorundan ayrı tutulur.

## Özel şirket tipi motorları

### Banka

Banka profili UFRS finansallarıyla değerlendirilir. Sanayi tipi FD/FAVÖK, FCF, net marj ve net borç/FAVÖK ana skora sokulmaz. Net kâr, net faiz geliri, net ücret/komisyon, kredi, mevduat/toplanan fon, aktif, özkaynak ve özkaynak/aktif gelişimi ayrı izlenir. Katılım bankalarındaki farklı satır isimleri için alias/fallback bulunur.

### Sigorta

Sigorta motoru sanayi şirketi ciro/FAVÖK/FCF mantığına zorlanmaz. Net yazılan primler, prim büyümesi, genel teknik bölüm dengesi, teknik denge/net yazılan prim oranı, net kâr büyümesi ve aktif/özkaynak gelişimi ayrı raporlanır.

### Banka dışı finansal şirketler

Finansal kiralama, faktoring, menkul değerler ve benzeri şirketlerde UFRS/XI_29 fallback uygulanır. Finans sektörü faaliyet sonucu, finansal alacaklar, finansal yükümlülükler, net kâr, aktif ve özkaynak trendi ayrı değerlendirilir. Sanayi tipi net marj/FAVÖK/FCF ana skora zorlanmaz.

### GYO

GYO'da klasik F/K, PD/DD ve FD/FAVÖK tek başına ucuzluk skoru üretmez. Gerçek NAD/PD-NAD, portföy ekspertiz değerleri, proje/arsa stoğu, satış ve teslim takvimi, finansman yapısı ve XGMYO relatif performansı önceliklidir. İş Yatırım bir gerçekleşen oranı A/D gösteriyorsa başka sağlayıcıdaki sayı gerçekleşen oran gibi skora sokulmaz.

### Holding ve Yatırım Ortaklığı

Holding/portföy yapılarında klasik konsolide sanayi çarpanları otomatik değerleme skoru üretmez. Esas değerleme için iştirak/portföy bazlı NAD gerekir.

data/nav_inputs.csv dosyasına güvenilir bir NAD girildiğinde sistem PD/NAD iskonto/primini hesaplar. Örnek satır:

    symbol,nav_total_try,as_of,source,note
    KCHOL,1000000000000,2026-09-30,Kaynak adı,Açıklama

NAD girilmemişse rapor VALUATION_PARTIAL / NAV_REQUIRED verir; tahmin uydurmaz.

## Rapor hazırlık durumu

Her rapor makine-okunur bir hazırlık statüsü taşır:

- READY
- READY_WITH_WARNINGS
- VALUATION_PARTIAL
- PARTIAL
- REVIEW

GYO/Holding için NAD yoksa tüm rapor bozuk sayılmaz; finansal analiz devam eder fakat değerleme katmanı kısmi olarak işaretlenir.

## Kaynak doğrulaması

TradingView, İş Yatırım şirket kartı ve mali tablodan türetilen metrikler karşılaştırılır. Rapor uyumlu değerleri, güncelleme/baz farklarını, büyük sağlayıcı farklarını ve TMS 29 / yeniden ifade kaynaklı olası ayrışmaları ayrı gösterir. Veri güveni düşükse profesyonel sonuç daha temkinli yazılır; kaynak farkı sessizce ortalanmaz.

## Tüm BIST kalite denetimi

.github/workflows/full_bist_audit.yml güncel BIST evrenini 8 paralel parçaya bölerek şirket şirket denetler.

Denetlenen başlıca kurallar:

- profil sınıflandırması,
- banka/GYO/holding/sigorta/finansal kurum kuralları,
- özel profil motorlarının çalışması,
- negatif özkaynak ve anlamsız payda korumaları,
- negatif/sıfır değerleme çarpanlarının yanlış ucuz skorlanmaması,
- finansal tablo kapsaması,
- İş Yatırım–TradingView farkları,
- skor/yüzdelik matematik sınırları,
- XBANK/XGMYO vb. sektör endeksi eşleşmeleri.

Çıktı dosyaları full_bist_audit.csv, full_bist_audit_summary.json ve full_bist_audit.md olur. Veri sağlayıcısında tarihsel finansal bulunmaması motor hatasıyla aynı şey değildir; veri eksikliği ayrı sınıflandırılır.

## Regresyon seti

Temsili profiller otomatik test edilir:

- ASELS — sanayi/savunma
- AKBNK — banka
- ALBRK — katılım bankası
- EKGYO — GYO / NAD kapısı
- KCHOL — holding / NAD kapısı
- AGESA — sigorta
- GLBMD — banka dışı finansal
- ISFIN — tarihsel veri yoksa graceful fallback

## Çıktılar

Bir analiz artifact'ında veri bulunabildiği ölçüde SEMBOL_report.html, SEMBOL_report.json, SEMBOL_universe_snapshot.csv, 12 çeyreklik bilanço/gelir/nakit akışı CSV'leri ve yıllık gelir/bilanço CSV'leri oluşur.

## Dosya yapısı

    analyze.py
    history_engine.py
    special_profiles.py
    audit_all.py
    audit_merge.py
    regression_checks.py
    data/nav_inputs.csv
    .github/workflows/analyze.yml
    .github/workflows/regression.yml
    .github/workflows/full_bist_audit.yml

## Sınırlar

- GYO/Holding gerçek NAD verisi güvenilir bir kaynaktan gelmiyorsa sistem bunu uydurmaz.
- Sağlayıcıların raporlama zamanı ve TMS 29 bazları farklı olabilir.
- Bazı yeni/özel finansal şirketlerde tarihsel tablo sağlayıcıda bulunmayabilir; rapor PARTIAL olarak devam eder.
- Skorlar araştırma modelidir; al/sat kararı değildir.

## v1.0 doğrulama durumu

v1.0 motoru temsili profil regresyon setini başarıyla geçmiştir. Son tam BIST denetiminde 621 benzersiz şirket ve 100/100 XU100 bileşeni kontrol edilmiş; motor seviyesinde ERROR veya CRITICAL bulgu kalmamıştır. Kalan uyarılar veri sağlayıcı farkı, ekonomik olarak anlamsız negatif çarpanlar, sınırlı tarihçe veya sağlayıcıda bulunmayan finansallar gibi veri-kalite başlıkları olarak ayrı tutulur.

## Uyarı

Bu proje araştırma ve veri analizi amaçlıdır. Üretilen raporlar yatırım tavsiyesi değildir.
