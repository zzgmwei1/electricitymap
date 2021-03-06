from bs4 import BeautifulSoup
from collections import defaultdict
import arrow, os, re, requests

ENTSOE_ENDPOINT = 'https://transparency.entsoe.eu/api'
ENTSOE_PARAMETER_DESC = {
    'B01': 'Biomass',
    'B02': 'Fossil Brown coal/Lignite',
    'B03': 'Fossil Coal-derived gas',
    'B04': 'Fossil Gas',
    'B05': 'Fossil Hard coal',
    'B06': 'Fossil Oil',
    'B07': 'Fossil Oil shale',
    'B08': 'Fossil Peat',
    'B09': 'Geothermal',
    'B10': 'Hydro Pumped Storage',
    'B11': 'Hydro Run-of-river and poundage',
    'B12': 'Hydro Water Reservoir',
    'B13': 'Marine',
    'B14': 'Nuclear',
    'B15': 'Other renewable',
    'B16': 'Solar',
    'B17': 'Waste',
    'B18': 'Wind Offshore',
    'B19': 'Wind Onshore',
    'B20': 'Other',
}
ENTSOE_PARAMETER_BY_DESC = {v: k for k, v in ENTSOE_PARAMETER_DESC.iteritems()}
# Define all ENTSOE country_code <-> domain mapping
ENTSOE_DOMAIN_MAPPINGS = {
    'AL': '10YAL-KESH-----5',
    'AT': '10YAT-APG------L',
    'BE': '10YBE----------2',
    'BG': '10YCA-BULGARIA-R',
    'CH': '10YCH-SWISSGRIDZ',
    'CZ': '10YCZ-CEPS-----N',
    'DE': '10Y1001A1001A83F',
    'DK': '10Y1001A1001A65H',
    'EE': '10Y1001A1001A39I',
    'ES': '10YES-REE------0',
    'FI': '10YFI-1--------U',
    'FR': '10YFR-RTE------C',
    'GB': '10YGB----------A',
    'GR': '10YGR-HTSO-----Y',
    'HR': '10YHR-HEP------M',
    'HU': '10YHU-MAVIR----U',
    'IE': '10YIE-1001A00010',
    'IT': '10YIT-GRTN-----B',
    'LT': '10YLT-1001A0008Q',
    'LV': '10YLV-1001A00074',
    # 'MD': 'MD',
    'MK': '10YMK-MEPSO----8',
    'MT': '10Y1001A1001A93C',
    'NL': '10YNL----------L',
    'NO': '10YNO-0--------C',
    'PL': '10YPL-AREA-----S',
    'PT': '10YPT-REN------W',
    'RO': '10YRO-TEL------P',
    'RS': '10YCS-SERBIATSOV',
    'SE': '10YSE-1--------K',
    'SI': '10YSI-ELES-----O',
    'SK': '10YSK-SEPS-----K',
    # 'TR': 'TR',
    # 'UA': 'UA'
}

def query_consumption(domain, session):
    now = arrow.utcnow()
    params = {
        'documentType': 'A65',
        'processType': 'A16',
        'outBiddingZone_Domain': domain,
        'periodStart': now.replace(hours=-24).format('YYYYMMDDHH00'),
        'periodEnd': now.replace(hours=+24).format('YYYYMMDDHH00'),
        'securityToken': os.environ['ENTSOE_TOKEN']
    }
    response = session.get(ENTSOE_ENDPOINT, params=params)
    if response.ok: return response.text
    else:
        # Grab the error if possible
        soup = BeautifulSoup(response.text, 'html.parser')
        raise Exception('Failed to get consumption. Reason: %s' % soup.find_all('text')[0].contents[0])

def query_production(psr_type, in_domain, session):
    now = arrow.utcnow()
    params = {
        'psrType': psr_type,
        'documentType': 'A75',
        'processType': 'A16',
        'in_Domain': in_domain,
        'periodStart': now.replace(hours=-24).format('YYYYMMDDHH00'),
        'periodEnd': now.replace(hours=+24).format('YYYYMMDDHH00'),
        'securityToken': os.environ['ENTSOE_TOKEN']
    }
    response = session.get(ENTSOE_ENDPOINT, params=params)
    if response.ok: return response.text
    else:
        return # Return by default
        # Grab the error if possible
        soup = BeautifulSoup(response.text, 'html.parser')
        print 'Failed for psr %s' % psr_type
        print 'Reason:', soup.find_all('text')[0].contents[0]

def query_exchange(in_domain, out_domain, session):
    now = arrow.utcnow()
    params = {
        'documentType': 'A11',
        'in_Domain': in_domain,
        'out_Domain': out_domain,
        'periodStart': now.replace(hours=-24).format('YYYYMMDDHH00'),
        'periodEnd': now.replace(hours=+24).format('YYYYMMDDHH00'),
        'securityToken': os.environ['ENTSOE_TOKEN']
    }
    response = session.get(ENTSOE_ENDPOINT, params=params)
    if response.ok: return response.text
    else:
        # Grab the error if possible
        soup = BeautifulSoup(response.text, 'html.parser')
        raise Exception('Failed to get exchange. Reason: %s' % soup.find_all('text')[0].contents[0])

def datetime_from_position(start, position, resolution):
    m = re.search('PT(\d+)([M])', resolution)
    if m:
        digits = int(m.group(1))
        scale = m.group(2)
        if scale == 'M':
            return start.replace(minutes=position * digits)
    raise NotImplementedError('Could not recognise resolution %s' % resolution)

def parse_consumption(xml_text):
    if not xml_text: return None
    soup = BeautifulSoup(xml_text, 'html.parser')
    # Get all points
    quantities = []
    datetimes = []
    for timeseries in soup.find_all('timeseries'):
        resolution = timeseries.find_all('resolution')[0].contents[0]
        datetime_start = arrow.get(timeseries.find_all('start')[0].contents[0])
        for entry in timeseries.find_all('point'):
            quantities.append(float(entry.find_all('quantity')[0].contents[0]))
            position = int(entry.find_all('position')[0].contents[0])
            datetimes.append(datetime_from_position(datetime_start, position, resolution))
    return quantities, datetimes

def parse_production(xml_text):
    if not xml_text: return None
    soup = BeautifulSoup(xml_text, 'html.parser')
    # Get all points
    quantities = []
    datetimes = []
    for timeseries in soup.find_all('timeseries'):
        resolution = timeseries.find_all('resolution')[0].contents[0]
        datetime_start = arrow.get(timeseries.find_all('start')[0].contents[0])
        is_production = len(timeseries.find_all('inBiddingZone_Domain.mRID'.lower())) > 0
        for entry in timeseries.find_all('point'):
            quantity = float(entry.find_all('quantity')[0].contents[0])
            # If this is not a production, then it is storage (consumption)
            if not is_production: quantity *= -1
            position = int(entry.find_all('position')[0].contents[0])
            datetime = datetime_from_position(datetime_start, position, resolution)
            # Find out whether or not we should update the net production
            try:
                i = datetimes.index(datetime)
                quantities[i] += quantity
            except ValueError: # Not in list
                quantities.append(quantity)
                datetimes.append(datetime)
    return quantities, datetimes

def parse_exchange(xml_text, is_import, quantities=None, datetimes=None):
    if not xml_text: return None
    if not quantities: quantities = []
    if not datetimes: datetimes = []
    soup = BeautifulSoup(xml_text, 'html.parser')
    # Get all points
    for timeseries in soup.find_all('timeseries'):
        resolution = timeseries.find_all('resolution')[0].contents[0]
        datetime_start = arrow.get(timeseries.find_all('start')[0].contents[0])
        for entry in timeseries.find_all('point'):
            quantity = float(entry.find_all('quantity')[0].contents[0])
            if not is_import: quantity *= -1
            position = int(entry.find_all('position')[0].contents[0])
            datetime = datetime_from_position(datetime_start, position, resolution)
            # Find out whether or not we should update the net production
            try:
                i = datetimes.index(datetime)
                quantities[i] += quantity
            except ValueError: # Not in list
                quantities.append(quantity)
                datetimes.append(datetime)
    return quantities, datetimes

def get_biomass(values):
    if 'Biomass' in values or 'Fossil Peat' in values or 'Waste' in values:
        return values.get('Biomass', 0) + \
            values.get('Fossil Peat', 0) + \
            values.get('Waste', 0)

def get_coal(values):
    if 'Fossil Brown coal/Lignite' in values or 'Fossil Hard coal' in values:
        return values.get('Fossil Brown coal/Lignite', 0) + \
            values.get('Fossil Hard coal', 0)

def get_gas(values):
    if 'Fossil Coal-derived gas' in values or 'Fossil Gas' in values:
        return values.get('Fossil Coal-derived gas', 0) + \
            values.get('Fossil Gas', 0)

def get_hydro(values):
    if 'Hydro Pumped Storage' in values \
        or 'Hydro Run-of-river and poundage' in values \
        or 'Hydro Water Reservoir' in values:
        return max(values.get('Hydro Pumped Storage', 0), 0) + \
            values.get('Hydro Run-of-river and poundage', 0) + \
            values.get('Hydro Water Reservoir', 0)

def get_oil(values):
    if 'Fossil Oil' in values or 'Fossil Oil shale' in values:
        value = values.get('Fossil Oil', 0) + values.get('Fossil Oil shale', 0)
        return value if value != -1.0 else None

def get_wind(values):
    if 'Wind Onshore' in values or 'Wind Offshore' in values:
        return values.get('Wind Onshore', 0) + values.get('Wind Offshore', 0)

def get_unknown(values):
    if 'Geothermal' in values \
        or 'Marine' in values \
        or 'Other renewable' in values \
        or 'Other' in values:
        return values.get('Geothermal', 0) + \
            values.get('Marine', 0) + \
            values.get('Other renewable', 0) + \
            values.get('Other', 0)

def fetch_consumption(country_code, session=None):
    if not session: session = requests.session()
    domain = ENTSOE_DOMAIN_MAPPINGS[country_code]
    # Grab consumption
    parsed = parse_consumption(query_consumption(domain, session))
    if parsed:
        quantities, datetimes = parsed
        data = {
            'countryCode': country_code,
            'datetime': datetimes[-1].datetime,
            'consumption': quantities[-1],
            'source': 'entsoe.eu'
        }

        return data

def fetch_production(country_code, session=None):
    if not session: session = requests.session()
    domain = ENTSOE_DOMAIN_MAPPINGS[country_code]
    # Create a double hashmap with keys (datetime, parameter)
    production_hashmap = defaultdict(lambda: {})
    # Grab production
    for k in ENTSOE_PARAMETER_DESC.keys():
        parsed = parse_production(query_production(k, domain, session))
        if parsed:
            quantities, datetimes = parsed
            for i in range(len(quantities)):
                production_hashmap[datetimes[i]][k] = quantities[i]


    # Take the last production date that is present for all parameters
    production_dates = sorted(set(production_hashmap.keys()), reverse=True)
    # Remove all dates in the future
    production_dates = filter(lambda x: x <= arrow.now(), production_dates)
    if not len(production_dates): return None
    production_dates_with_counts = map(lambda date: len(production_hashmap[date].keys()),
        production_dates)
    production_date = production_dates[production_dates_with_counts.index(max(production_dates_with_counts))]

    values = {ENTSOE_PARAMETER_DESC[k]: v for k, v in production_hashmap[production_date].iteritems()}

    data = {
        'countryCode': country_code,
        'datetime': production_date.datetime,
        'production': {
            'biomass': values.get('Biomass', None),
            'coal': get_coal(values),
            'gas': get_gas(values),
            'hydro': get_hydro(values),
            'nuclear': values.get('Nuclear', None),
            'oil': get_oil(values),
            'solar': values.get('Solar', None),
            'wind': get_wind(values),
            'unknown': get_unknown(values)
        },
        'source': 'entsoe.eu'
    }

    return data

def fetch_exchange(country_code1, country_code2, session=None):
    if not session: session = requests.session()
    domain1 = ENTSOE_DOMAIN_MAPPINGS[country_code1]
    domain2 = ENTSOE_DOMAIN_MAPPINGS[country_code2]
    # Create a hashmap with key (datetime)
    exchange_hashmap = {}
    # Grab exchange
    # Import
    parsed = parse_exchange(
        query_exchange(domain1, domain2, session),
        is_import=True)
    if parsed:
        # Export
        parsed = parse_exchange(
            xml_text=query_exchange(domain2, domain1, session),
            is_import=False, quantities=parsed[0], datetimes=parsed[1])
        if parsed:
            quantities, datetimes = parsed
            for i in range(len(quantities)):
                exchange_hashmap[datetimes[i]] = quantities[i]

    # Find the closest matching exchange
    sorted_country_codes = sorted([country_code1, country_code2])
    exchange_dates = sorted(set(exchange_hashmap.keys()), reverse=True)
    # Remove all dates in the future
    exchange_dates = filter(lambda x: x <= arrow.now(), exchange_dates)
    if not len(exchange_dates): return None
    exchange_date = exchange_dates[0]
    netFlow = exchange_hashmap[exchange_date]
    return {
        'sortedCountryCodes': '->'.join(sorted_country_codes),
        'datetime': exchange_date.datetime,
        'netFlow': netFlow if country_code1[0] == sorted_country_codes else -1 * netFlow,
        'source': 'entsoe.eu'
    }
