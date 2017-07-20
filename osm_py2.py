
# coding: utf-8

# In[1]:

import xml.etree.cElementTree as ET
import pprint
import re
from collections import defaultdict
import csv
import codecs
import cerberus
import sqlite3

import schema


# In[20]:

#!/usr/bin/env python

#Section 1: Get partial records from original xml file

OSM_FILE = "shanghai_china.osm"  # Replace this with your osm file
SAMPLE_FILE = "shanghai_sample.osm"

k = 100 # Parameter: take every k-th top level element
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag
Reference:
    http://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    context = iter(ET.iterparse(osm_file, events=('start', 'end')))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()
            
with open(SAMPLE_FILE, 'wb') as output:
    output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    output.write('<osm>\n  ')

    # Write every kth top level element
    for i, element in enumerate(get_element(OSM_FILE)):
        if i % k == 0:
            output.write(ET.tostring(element, encoding='utf-8'))

    output.write('</osm>')


# In[2]:

shanghai = "shanghai_sample.osm" #smaller file for faster process


# In[11]:

#Section 2: get number of tags

def count_tags(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    tag_list = {}
    for row in root.iter():
        if row.tag not in tag_list:
            tag_list[row.tag] = 1
        else:
            tag_list[row.tag] +=1
    return tag_list


# In[21]:

count_tags(shanghai)


# In[23]:

#Section 3: Check to see the types of tags

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')


def key_type(element, keys):
    if element.tag == "tag":
        if lower.search(element.attrib["k"]):
            keys["lower"] += 1
        elif lower_colon.search(element.attrib["k"]):
            keys["lower_colon"] += 1
        elif problemchars.search(element.attrib["k"]):
            keys["problemchars"] += 1
        else:
            keys["other"] +=1
        
    return keys

def find_colon(element, c_list):
    if element.tag == 'tag':
        if lower_colon.search(element.attrib["k"]):
            if element.attrib["k"] not in c_list:
                c_list[element.attrib["k"]] = 1
            else:
                c_list[element.attrib["k"]] += 1
    return c_list

def process_map(filename):
    keys = {"lower": 0, "lower_colon": 0, "problemchars": 0, "other": 0}
    colon_list = {}
    for _, element in ET.iterparse(filename):
        keys = key_type(element, keys)
        colon_list = find_colon(element, colon_list)
    return keys, colon_list


# In[24]:

keys = process_map(shanghai)
pprint.pprint(keys)


# In[25]:

# Section 4 Optional: Check to see the value in name:en attribute

def process_road_name(filename):
    en_roads = set()
    for _, element in ET.iterparse(filename):
        if element.tag == 'tag':
                if element.attrib['k'] == 'name:en':
                    if element.attrib['v'] not in en_roads:
                        en_roads.add(element.attrib['v'])
                    else:
                        pass

    return en_roads


# In[26]:

pprint.pprint(process_road_name(shanghai))


# In[27]:

#Section 4: Check to see possible errors


OSMFILE = "shanghai_sample.osm"
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)
ewsn_street_re = re.compile(r"\(([ewsn]|.)*\)", re.IGNORECASE)


expected = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", 
            "Trail", "Parkway", "Commons", "Expressway", "Highway", "Tunnel", "River", "Campus", "Park", "River", "Mall", "Plaza", "Bridge", "Museum", "School"]

# UPDATE THIS VARIABLE
mapping = { "St": "Street",
            "St.": "Street",
            "Hwy": "Highway",
            "Hwy.": "Highway",
            "Rd.": "Road",
            "Rd": "Road",
           "Ave": "Avenue",
           "Ave.": "Avenue",
           "(S)": "South",
           "(N)": "North",
           "(W)": "West",
           "(E)": "East",
           "(S.)": "South",
           "(N.)": "North",
           "(W.)": "West",
           "(E.)": "East",
           "Lu": "Road",
            }


def audit_street_type(street_types, street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)


def is_english_name(elem):
    return (elem.attrib['k'] == "name:en")


def audit(osmfile):
    osm_file = open(osmfile, "r")
    street_types = defaultdict(set)
    for _, elem in ET.iterparse(osm_file):
        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                if is_english_name(tag):
                    audit_street_type(street_types, tag.attrib['v'])
                    #tag.attrib['v'] = update_name(tag.attrib['v'], mapping)
    osm_file.close()
    return street_types

#Section 5: name change function

def update_name(name, mapping):
    m = street_type_re.search(name)
    eswn = ewsn_street_re.search(name)
    better_name = name
    # condition: if the street name does have a last word
    if m:
        # check if the street type is a key in your mapping dictionary:
        if m.group() in mapping.keys():
            better_street_type = mapping[m.group()]
            better_name = street_type_re.sub(better_street_type, name)
    
    # if road ends in (S) and similar types, make correction. 
    if eswn:
        if eswn.group() in mapping.keys():
            better_street_type = mapping[eswn.group()]
            better_name = ewsn_street_re.sub(better_street_type, name)
        st_list = better_name.split()
        old_end = st_list[-1]
        del st_list[-1]
        st_list.insert(0, old_end)
        not_better_name = ' '.join(st_list)
        d = street_type_re.search(not_better_name)
        if d:
            if d.group() in mapping.keys():
                better_street_type = mapping[d.group()]
                better_name = street_type_re.sub(better_street_type, not_better_name)
        
    return better_name


def test():
    st_types = audit(OSMFILE)
    pprint.pprint(dict(st_types))

    for st_type, ways in st_types.items():
        for name in ways:
            better_name = update_name(name, mapping)
            print(name, "=>", better_name)
            
if __name__ == '__main__':
    test()


# In[28]:

#!/usr/bin/env python

# Section 6: make corrections and save the result to csv


OSM_PATH = "shanghai_sample.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements
    
    if element.tag == 'node':
        for key in element.attrib.keys():
            if key in node_attr_fields:
                node_attribs[key] = element.attrib[key]
        for child in element:
            if child.tag == 'tag':
                if problem_chars.search(child.attrib['k']):
                    pass
                else:
                    tags_list = {}
                    tags_list['id'] = element.attrib['id']
                    if child.attrib['k'] == 'name:en':
                        tags_list['value'] = update_name(child.attrib['v'], mapping)
                    else:
                        tags_list['value'] = child.attrib['v']
                    if LOWER_COLON.search(child.attrib['k']):
                        colon_position = child.attrib['k'].find(':')
                        tags_list['key'] = child.attrib['k'][colon_position+1:]
                        tags_list['type'] = child.attrib['k'][:colon_position]
                    else:
                        tags_list['key'] = child.attrib['k']
                        tags_list['type'] = 'regular'
                    tags.append(tags_list)    
        
    if element.tag == 'way':
        for key in element.attrib.keys():
            if key in way_attr_fields:
                way_attribs[key] = element.attrib[key]
        position = 0
        for child in element:
            
            if child.tag == 'nd':
                way_nodes_list = {}
                way_nodes_list['id'] = element.attrib['id']
                way_nodes_list['node_id'] = child.attrib['ref']
                way_nodes_list['position'] = position
                position += 1
                way_nodes.append(way_nodes_list)
            if child.tag == 'tag':
                if problem_chars.search(child.attrib['k']):
                    pass
                else:
                    tags_list = {}
                    tags_list['id'] = element.attrib['id']
                    if child.attrib['k'] == 'name:en':
                        tags_list['value'] = update_name(child.attrib['v'], mapping)
                    else:
                        tags_list['value'] = child.attrib['v']
                    if LOWER_COLON.search(child.attrib['k']):
                        colon_position = child.attrib['k'].find(':')
                        tags_list['key'] = child.attrib['k'][colon_position+1:]
                        tags_list['type'] = child.attrib['k'][:colon_position]
                    else:
                        tags_list['key'] = child.attrib['k']
                        tags_list['type'] = 'regular'
                    tags.append(tags_list)  
            
    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file,          codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file,          codecs.open(WAYS_PATH, 'w') as ways_file,          codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file,          codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=True)


# In[32]:

#Section 7: Create db file from all csv files

osmdb = 'osm2.db'

connection = sqlite3.connect(osmdb)
write_cursor = connection.cursor()
write_cursor.execute('''
                    CREATE TABLE nodes(id INTEGER, lat TEXT, lon TEXT, user TEXT, uid INTEGER, version TEXT, changeset TEXT, timestamp TEXT)''')

connection.commit()

with open('nodes.csv', 'r') as csvfile:
    middleman = csv.DictReader(csvfile) # comma is default delimiter
    to_db = [(i['id'].decode("utf-8"), i['lat'].decode("utf-8"), i['lon'].decode("utf-8"), i['user'].decode("utf-8"), i["uid"].decode("utf-8"), i["version"].decode("utf-8"),i["changeset"].decode("utf-8"),i["timestamp"].decode("utf-8")) for i in middleman]

write_cursor.executemany("INSERT INTO nodes (id, lat, lon, user, uid, version, changeset, timestamp) VALUES (?,?,?,?,?,?,?,?);", to_db)

connection.commit()
connection.close()


# In[40]:

connection = sqlite3.connect(osmdb)
write_cursor = connection.cursor()
write_cursor.execute('''
                    CREATE TABLE nodes_tags(id INTEGER, key TEXT, value TEXT, type TEXT)''')

connection.commit()

with open('nodes_tags.csv', 'r') as csvfile:
    middleman = csv.DictReader(csvfile) # comma is default delimiter
    to_db = [(i['id'].decode("utf-8"), i['key'].decode("utf-8"), i['value'].decode("utf-8"), i['type'].decode("utf-8")) for i in middleman]

write_cursor.executemany("INSERT INTO nodes_tags(id, key, value, type) VALUES (?,?,?,?);", to_db)

connection.commit()
connection.close()


# In[44]:

connection = sqlite3.connect(osmdb)
write_cursor = connection.cursor()
write_cursor.execute('''DROP TABLE ways_nodes ''')
connection.commit()


# In[41]:

connection = sqlite3.connect(osmdb)
write_cursor = connection.cursor()
write_cursor.execute('''
                    CREATE TABLE ways(id INTEGER, user TEXT, uid TEXT, version TEXT, changeset TEXT, timestamp TEXT)''')

connection.commit()

with open('ways.csv', 'r') as csvfile:
    middleman = csv.DictReader(csvfile) # comma is default delimiter
    to_db = [(i['id'].decode("utf-8"), i['user'].decode("utf-8"), i['uid'].decode("utf-8"), i['version'].decode("utf-8"), i["changeset"].decode("utf-8"), i["timestamp"].decode("utf-8")) for i in middleman]

write_cursor.executemany("INSERT INTO ways (id, user, uid, version, changeset, timestamp) VALUES (?,?,?,?,?,?);", to_db)

connection.commit()
connection.close()


# In[42]:

connection = sqlite3.connect(osmdb)
write_cursor = connection.cursor()
write_cursor.execute('''
                    CREATE TABLE ways_tags(id INTEGER, key TEXT, value TEXT, type TEXT)''')

connection.commit()

with open('ways_tags.csv', 'r') as csvfile:
    middleman = csv.DictReader(csvfile) # comma is default delimiter
    to_db = [(i['id'].decode("utf-8"), i['key'].decode("utf-8"), i['value'].decode("utf-8"), i['type'].decode("utf-8")) for i in middleman]

write_cursor.executemany("INSERT INTO ways_tags(id, key, value, type) VALUES (?,?,?,?);", to_db)

connection.commit()
connection.close()


# In[45]:

connection = sqlite3.connect(osmdb)
write_cursor = connection.cursor()
write_cursor.execute('''
                    CREATE TABLE ways_nodes(id INTEGER, node_id INTEGER, position INTEGER)''')

connection.commit()

with open('ways_nodes.csv', 'r') as csvfile:
    middleman = csv.DictReader(csvfile) # comma is default delimiter
    to_db = [(i['id'].decode("utf-8"), i['node_id'].decode("utf-8"), i['position'].decode("utf-8")) for i in middleman]

write_cursor.executemany("INSERT INTO ways_nodes(id, node_id, position) VALUES (?,?,?);", to_db)

connection.commit()
connection.close()


# In[4]:

#section 8: Additional error

def process_regular_name(filename):
    en_roads = set()
    for _, element in ET.iterparse(filename):
        if element.tag == 'tag':
                if element.attrib['k'] == 'name':
                    if element.attrib['v'] not in en_roads:
                        en_roads.add(element.attrib['v'])
                    else:
                        pass

    return en_roads

pprint.pprint(process_regular_name(shanghai))


# In[ ]:



