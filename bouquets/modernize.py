import os
import re

bouquet_dir = os.path.dirname(os.path.abspath(__file__))
lamedb_path = os.path.join(bouquet_dir, 'lamedb')

# 1. Parse lamedb to map channel references to names and providers
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
                    
                    provider_raw = ''
                    if i + 2 < len(lines):
                        line3 = lines[i+2].strip()
                        if line3.startswith('p:'):
                            prov_part = line3.split(',')[0]
                            if ':' in prov_part:
                                provider_raw = prov_part.split(':', 1)[1].strip()
                                
                    services[key] = (name, provider_raw)
                    i += 3
                else:
                    i += 1
    except Exception as e:
        print('Error parsing lamedb: ' + str(e))

print('Loaded ' + str(len(services)) + ' channel names from lamedb.')

# 2. Find all Turksat bouquets (both raw and already modernized)
files = [f for f in os.listdir(bouquet_dir) if (
    f.startswith('userbouquet.420e_') or 
    f.startswith('userbouquet.tr_') or 
    f.startswith('userbouquet.digiturk_') or 
    f.startswith('userbouquet.dsmart_') or 
    f.startswith('userbouquet.tivibu_')
) and f.endswith('.tv')]

# Provider key mapping
provider_mapping = {
    'Digital Platform': 'digiturk',
    'D-Smart': 'dsmart',
    'D-SMART': 'dsmart',
    'DOGAN TV': 'dsmart',
    'DOGAN': 'dsmart',
    'DEMIROREN MEDYA': 'dsmart',
    'DEMIROREN': 'dsmart',
    'TTNET': 'tivibu',
    'TURKSAT': 'tr',
    'TÜRKSAT': 'tr',
    'TRT': 'tr',
    'TÜRK TELEKOM': 'tivibu',
    'TURK TELEKOM': 'tivibu',
}

provider_display_names = {
    'tr': 'Türksat',
    'digiturk': 'Digiturk',
    'dsmart': 'D-Smart',
    'tivibu': 'Tivibu'
}

# 3. Read channels and prevent duplicates
unique_channels = {}  # sref -> (clean_name, provider_key)
import re

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
                name_override = ''
                if len(parts_sref) >= 2 and '::' in parts_sref[1]:
                    sref_part, name_override = parts_sref[1].split('::', 1)
                    sref_full = sref_part + ':'
                elif ':' in parts_sref[1] and len(parts_sref[1].split(':')) > 10:
                    parts_colons = parts_sref[1].split(':')
                    name_override = parts_colons[-1]
                    sref_full = ':'.join(parts_colons[:10]) + ':'
                
                parts = sref_full.split(':')
                if len(parts) >= 7:
                    srv_id = parts[3].lower().lstrip('0')
                    ts_id = parts[4].lower().lstrip('0')
                    net_id = parts[5].lower().lstrip('0')
                    
                    name, provider_raw = services.get((srv_id, ts_id, net_id), ('Unknown', ''))
                    if name == 'Unknown' and name_override:
                        name = name_override
                    
                    # Clean up name (remove provider suffixes)
                    name_clean = re.sub(r'\s*\((Digiturk|D-Smart|Tivibu|FTA|Turksat)\)', '', name, flags=re.IGNORECASE)
                    
                    provider_key = provider_mapping.get(provider_raw, 'tr')
                    sref_standard = ':'.join(parts[:7]) + ':0:0:0:'
                    
                    if sref_standard not in unique_channels:
                        unique_channels[sref_standard] = (name_clean, provider_key)

print('Found ' + str(len(unique_channels)) + ' unique Turksat channels.')

# 4. Classify channels into composite categories: (provider_key, genre_key)
categories = {}
genres = {
    'national': 'Ulusal',
    'news': 'Haberler',
    'sports': 'Spor',
    'movies': 'Sinema & Dizi',
    'documentary': 'Belgesel',
    'kids': 'Çocuk',
    'music': 'Müzik',
    'others': 'Diğer'
}

# Initialize categories
for p_key in provider_display_names.keys():
    for g_key in genres.keys():
        categories[(p_key, g_key)] = []

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

for sref, (name, provider_key) in unique_channels.items():
    n = name.lower()
    
    if not name or name == 'Unknown' or any(k in n for k in ['test', 'data', 'sid ', 'ch-']):
        continue

    # Classify genre
    genre_key = 'others'
    if any(k in n for k in ['çocuk', 'cocuk', 'minika', 'cartoon', 'disney', 'nickelodeon', 'baby tv', 'trtcocuk']):
        genre_key = 'kids'
    elif any(k in n for k in ['müzik', 'muzik', 'dream tv', 'power', 'number one', 'kral', 'türkpop', 'number1', 'powerturk']):
        genre_key = 'music'
    elif any(k in n for k in ['haber', 'ntv', 'cnn', 'tgrt', 'tvnet', 'halk', 'tele1', 'sözcü', 'szc', 'ekol', 'bloomberg', 'a para', '24 hd', 'global']):
        genre_key = 'news'
    elif any(k in n for k in ['spor', 's sport', 'eurosport', 'bein sports', 'bein sport', 'tivibu spor', 'sportstv']):
        genre_key = 'sports'
    elif any(k in n for k in ['belgesel', 'yaban', 'history', 'nat geo', 'national geo', 'discovery']):
        genre_key = 'documentary'
    elif any(k in n for k in ['sinema', 'movie', 'dizi', 'action', 'cinema', 'd-smart', 'film', 'tv2', 'teve2', 'tlc', 'dmax']):
        genre_key = 'movies'
    elif any(k in n for k in ['trt 1', 'atv', 'star', 'show', 'kanal d', 'now', 'fox', 'tv8', 'kanal 7', 'tv8.5', 'beyaz', 'trt1', 'kanald', 'show tv', 'star tv', 'trt 1 hd']):
        genre_key = 'national'
        
    categories[(provider_key, genre_key)].append((name, sref))

# Sort channels within categories
for key in categories.keys():
    p_key, g_key = key
    if g_key == 'national':
        categories[key].sort(key=lambda x: get_national_priority(x[0]))
    else:
        categories[key].sort(key=lambda x: x[0])

# 5. Write separate modular files and generate bouquets.tv index
generated_files = set()
bouquets_tv_entries = []

# Define desired ordering for bouquets.tv
provider_order = ['tr', 'digiturk', 'dsmart', 'tivibu']
genre_order = ['national', 'news', 'sports', 'movies', 'documentary', 'kids', 'music', 'others']

for p_key in provider_order:
    p_display = provider_display_names[p_key]
    for g_key in genre_order:
        channels = categories[(p_key, g_key)]
        if channels:
            filename = 'userbouquet.{}_{}.tv'.format(p_key, g_key)
            displayName = '[42.0E] {} - {}'.format(p_display, genres[g_key])
            out_path = os.path.join(bouquet_dir, filename)
            
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write('#NAME {}\n'.format(displayName))
                for name, sref in channels:
                    f.write('#SERVICE {}:{}\n'.format(sref, name))
            
            print('Generated modular bouquet: {} with {} channels.'.format(filename, len(channels)))
            generated_files.add(filename)
            bouquets_tv_entries.append(filename)

# Ensure favourites.tv is present
fav_filename = 'userbouquet.favourites.tv'
fav_path = os.path.join(bouquet_dir, fav_filename)
if not os.path.exists(fav_path):
    with open(fav_path, 'w', encoding='utf-8') as f:
        f.write('#NAME Favourites (TV)\n')
    print('Created empty favourites bouquet.')
generated_files.add(fav_filename)

# Clean up all old modular bouquet files that are no longer active
for f in os.listdir(bouquet_dir):
    if f.startswith('userbouquet.') and f.endswith('.tv'):
        if f != fav_filename and f not in generated_files:
            os.remove(os.path.join(bouquet_dir, f))
            print('Removed obsolete bouquet file: ' + f)

# Write local bouquets.tv
bq_path = os.path.join(bouquet_dir, 'bouquets.tv')
with open(bq_path, 'w', encoding='utf-8') as f:
    f.write('#NAME User - Bouquets (TV)\n')
    f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet\n')
    for bq_file in bouquets_tv_entries:
        f.write('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{}" ORDER BY bouquet\n'.format(bq_file))

print('Successfully finalized bouquets.tv locally.')
