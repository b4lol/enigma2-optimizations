import os
import re

bouquet_dir = os.path.dirname(os.path.abspath(__file__))
lamedb_path = os.path.join(bouquet_dir, 'lamedb')

# 1. Parse lamedb to map channel references to names
services = {}
if os.path.exists(lamedb_path):
    try:
        with open(lamedb_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if 'services\n' in content:
            services_part = content.split('services\n')[-1].split('\nend')[0]
            lines = services_part.split('\n')
            i = 0
            while i < len(lines) - 2:
                line1 = lines[i].strip()
                if not line1:
                    i += 1
                    continue
                parts = line1.split(':')
                if len(parts) >= 5:
                    srv_id, namespace, ts_id, net_id, srv_type = parts[:5]
                    key = (srv_id.lower().lstrip('0'), ts_id.lower().lstrip('0'), net_id.lower().lstrip('0'))
                    name = lines[i+1].strip()
                    services[key] = name
                    i += 3
                else:
                    i += 1
    except Exception as e:
        print('Error parsing lamedb: ' + str(e))

print('Loaded ' + str(len(services)) + ' channel names from lamedb.')

# 2. Find all downloaded Turksat bouquets
files = [f for f in os.listdir(bouquet_dir) if f.startswith('userbouquet.420e_') and f.endswith('.tv')]

# 3. Read channels and prevent duplicates
unique_channels = {}
for filename in files:
    path = os.path.join(bouquet_dir, filename)
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith('#SERVICE'):
            parts_sref = line_stripped.split()
            if len(parts_sref) >= 2:
                sref_full = parts_sref[1]
                parts = sref_full.split(':')
                if len(parts) >= 7:
                    srv_id = parts[3].lower().lstrip('0')
                    ts_id = parts[4].lower().lstrip('0')
                    net_id = parts[5].lower().lstrip('0')
                    
                    ch_name = services.get((srv_id, ts_id, net_id), 'Unknown')
                    sref_standard = ':'.join(parts[:7]) + ':0:0:0:'
                    if sref_standard not in unique_channels:
                        unique_channels[sref_standard] = ch_name

print('Found ' + str(len(unique_channels)) + ' unique Turksat channels.')

# 4. Classify channels
categories = {
    'national': [],
    'news': [],
    'sports': [],
    'movies': [],
    'documentary': [],
    'kids': [],
    'music': [],
    'others': []
}

national_order = [
    'trt 1', 'trt1',
    'atv',
    'kanal d', 'kanald',
    'star',
    'show',
    'now', 'fox',
    'tv8',
    'tv8.5', 'tv8,5',
    'kanal 7', 'kanal7',
    'tlc',
    'dmax',
    'teve2', 'tv2',
    'beyaz',
    'sözcü', 'szc',
    'halk',
    'tele1'
]

def get_national_priority(name):
    n = name.lower()
    for idx, key in enumerate(national_order):
        if key in n:
            return idx
    return 999

for sref, name in unique_channels.items():
    n = name.lower()
    
    if not name or name == 'Unknown' or any(k in n for k in ['test', 'data', 'sid ', 'ch-']):
        continue

    # Kids
    if any(k in n for k in ['çocuk', 'cocuk', 'minika', 'cartoon', 'disney', 'nickelodeon', 'baby tv', 'trtcocuk']):
        categories['kids'].append((name, sref))
    # Music
    elif any(k in n for k in ['müzik', 'muzik', 'dream tv', 'power', 'number one', 'kral', 'türkpop', 'number1', 'powerturk']):
        categories['music'].append((name, sref))
    # News
    elif any(k in n for k in ['haber', 'ntv', 'cnn', 'tgrt', 'tvnet', 'halk', 'tele1', 'sözcü', 'szc', 'ekol', 'bloomberg', 'a para', '24 hd', 'global']):
        categories['news'].append((name, sref))
    # Sports
    elif any(k in n for k in ['spor', 's sport', 'eurosport', 'bein sports', 'bein sport', 'tivibu spor', 'sportstv']):
        categories['sports'].append((name, sref))
    # Documentary
    elif any(k in n for k in ['belgesel', 'yaban', 'history', 'nat geo', 'national geo', 'discovery']):
        categories['documentary'].append((name, sref))
    # Movies / Series
    elif any(k in n for k in ['sinema', 'movie', 'dizi', 'action', 'cinema', 'd-smart', 'film', 'tv2', 'teve2', 'tlc', 'dmax']):
        categories['movies'].append((name, sref))
    # National
    elif any(k in n for k in ['trt 1', 'atv', 'star', 'show', 'kanal d', 'now', 'fox', 'tv8', 'kanal 7', 'tv8.5', 'beyaz', 'trt1', 'kanald', 'show tv', 'star tv', 'trt 1 hd']):
        categories['national'].append((name, sref))
    else:
        categories['others'].append((name, sref))

# Sort channels within categories
categories['national'].sort(key=lambda x: get_national_priority(x[0]))
categories['news'].sort(key=lambda x: x[0])
categories['sports'].sort(key=lambda x: x[0])
categories['movies'].sort(key=lambda x: x[0])
categories['documentary'].sort(key=lambda x: x[0])
categories['kids'].sort(key=lambda x: x[0])
categories['music'].sort(key=lambda x: x[0])
categories['others'].sort(key=lambda x: x[0])

# 5. Write separate modular files
genre_files = {
    'national': ('userbouquet.tr_national.tv', '[42.0E] Türksat - Ulusal'),
    'news': ('userbouquet.tr_news.tv', '[42.0E] Türksat - Haberler'),
    'sports': ('userbouquet.tr_sports.tv', '[42.0E] Türksat - Spor'),
    'movies': ('userbouquet.tr_movies.tv', '[42.0E] Türksat - Sinema & Dizi'),
    'documentary': ('userbouquet.tr_documentary.tv', '[42.0E] Türksat - Belgesel'),
    'kids': ('userbouquet.tr_kids.tv', '[42.0E] Türksat - Çocuk'),
    'music': ('userbouquet.tr_music.tv', '[42.0E] Türksat - Müzik'),
    'others': ('userbouquet.tr_others.tv', '[42.0E] Türksat - Diğer')
}

for cat_key, (filename, displayName) in genre_files.items():
    channels = categories[cat_key]
    out_path = os.path.join(bouquet_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('#NAME {}\n'.format(displayName))
        for name, sref in channels:
            f.write('#SERVICE {}\n'.format(sref))
    print('Generated modular bouquet: ' + filename + ' with ' + str(len(channels)) + ' channels.')

# Ensure favourites.tv is present
fav_path = os.path.join(bouquet_dir, 'userbouquet.favourites.tv')
if not os.path.exists(fav_path):
    with open(fav_path, 'w', encoding='utf-8') as f:
        f.write('#NAME Favourites (TV)\n')
    print('Created empty favourites bouquet.')

# Clean up all old userbouquet.420e_*.tv files
for f in os.listdir(bouquet_dir):
    if f.startswith('userbouquet.420e_') and f.endswith('.tv'):
        os.remove(os.path.join(bouquet_dir, f))
        print('Removed old raw file: ' + f)

# Write local bouquets.tv containing only these modular satellite files
bq_path = os.path.join(bouquet_dir, 'bouquets.tv')
with open(bq_path, 'w', encoding='utf-8') as f:
    f.write('#NAME User - Bouquets (TV)\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_national.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_news.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_sports.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_movies.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_documentary.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_kids.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_music.tv" ORDER BY bouquet\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.tr_others.tv" ORDER BY bouquet\n')

print('Successfully finalized bouquets.tv locally.')
