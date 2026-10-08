# BIST Fundamental Intelligence

BIST hisseleri için otomatik temel analiz ve karşılaştırma motoru.

## MVP v0.1

Bir hisse kodu verildiğinde sistem:

- Temel finansal verileri toplar.
- F/K, PD/DD, ROE, ROA, ciro büyümesi, kâr/EPS büyümesi ve ek finansal faktörleri hesaplar.
- Hisseyi kendi başına `İyi / Nötr / Zayıf` olarak puanlar.
- Önce dar endüstri grubunu, yeterli emsal yoksa sektör/profil grubunu kullanarak emsal medyanı üretir.
- BIST100'e göre yaklaşık 3 ay / 6 ay / 12 ay relatif performans ve alfa hesaplar.
- HTML + JSON raporu üretir.
- Eksik veriyi uydurmaz; `N/A` olarak bırakır.

> İlk veri sağlayıcı Yahoo Finance'tır. BIST verilerinde eksik veya gecikmeli alanlar olabilir. Mimari daha sonra KAP/resmî veri kaynakları eklenebilecek şekilde geliştirilecektir.

## GitHub üzerinden deneme

1. Repository'de **Actions** sekmesine gir.
2. **Hisse Analizi** workflow'unu aç.
3. **Run workflow** seç.
4. `symbol` alanına örneğin `ASELS` yaz.
5. Çalışma tamamlandığında `bist-report-ASELS` artifact'ını indir.
6. İçindeki `ASELS_report.html` dosyasını aç.

## Windows'ta yerel kullanım

Python 3.11+ kurulu olmalı.

```powershell
pip install -r requirements.txt
python analyze.py ASELS
```

Daha kolay kullanım için:

```text
HISSE_ANALIZ.bat
```

dosyasına çift tıkla ve hisse kodunu yaz.

Raporlar `reports/` klasörüne gelir.

## İlk test hisseleri

- ASELS
- AKBNK
- TUPRS
- BIMAS
- THYAO

## Rapor yapısı

- Bireysel temel skor
- Finansal faktör bazlı mutlak puanlar
- Endüstri/sektör emsal medyanları
- Faktör bazlı relatif puanlar
- BIST100 3A / 6A / 12A relatif performansı
- Otomatik Türkçe yorum
- Kullanılan emsal evreni

## Yol haritası

- v0.1: Hisse kodu → HTML/JSON raporu
- v0.2: Tüm BIST hisse evreni ve sektör/endüstri haritası
- v0.3: KAP / resmî finansal veri katmanı
- v0.4: 3Y/5Y finansal trend, CAGR ve şirketin kendi tarihsel medyanı
- v0.5: Sektör ve BIST yüzdelik sıralamaları
- v0.6: Banka, GYO, Holding, Sigorta vb. özel analiz motorları
- v0.7: Telegram `/analiz ASELS`
- v1.0: Temel + teknik + relatif güç birleşik araştırma motoru

## Uyarı

Bu proje araştırma ve veri analizi amaçlıdır. Üretilen raporlar yatırım tavsiyesi değildir.
