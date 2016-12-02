from os import listdir
from os.path import isfile, join
import nltk
from datetime import datetime
from SPARQLWrapper import SPARQLWrapper, JSON
import string
import sys, http.client, urllib.request, urllib.parse, urllib.error, json


startTime = datetime.now()


corpus_root = "/Users/mattcallaway/nltk_data/corpora/wsj_untagged/"
output_root = "/Users/mattcallaway/nltk_data/corpora/wsj_output/"
named_entities_root = "/Users/mattcallaway/nltk_data/corpora/named_entities/"

# Load up grammar for regexp parser
grammar = open(named_entities_root + "grammar.txt").read()
cp = nltk.RegexpParser(grammar)
print("Loaded grammar and regexp parser")

# Load named entities extracted from training data as sets
training_people = set(open(named_entities_root + 'people.txt').read().splitlines())
training_organisations = set(open(named_entities_root + 'organizations.txt').read().splitlines())
training_locations = set(open(named_entities_root + 'locations.txt').read().splitlines())
print("Loaded training data sets")

# Load name file
male = set(open(named_entities_root + "names.male").read().splitlines())
female = set(open(named_entities_root + "names.female").read().splitlines())
firstnames = male.union(female)
family = set(open(named_entities_root + "names.family").read().splitlines())
print("Loaded name sets")

# Load IEER corpus add to training sets
ieer = nltk.corpus.ieer
docs = ieer.parsed_docs()
for doc in docs:
    for subtree in doc.text.subtrees():
        if subtree.label == "PERSON":
            training_people.add(" ".join(subtree.leaves()))
        elif subtree.label == "LOCATION":
            training_locations.add(" ".join(subtree.leaves()))
        elif subtree.label == "ORGANIZATION":
            training_organisations.add(" ".join(subtree.leaves()))
print("IEER corpus loaded and added to training sets")

# Load entities from bigentitylist.txt
big_entity_list = open(named_entities_root + 'bigentitylist.txt').read().splitlines()
for line in big_entity_list:
    split = line.split()
    if split[0] == 'PER':
        training_people.add(split[1])
    elif split[0] == 'LOC':
        training_locations.add(split[1])
    elif split[0] == 'ORG':
        training_organisations.add(split[1])
print('Entities from bigentitylist.txt added to training sets')

# =================================
# =================================
#     Check DBPedia for string
# =================================
# =================================
def check_wiki(words):
    words_stripped = words
    for char in string.punctuation:
        words_stripped = words_stripped.replace(char, '')
    print('checking wiki for ->>> ' + words_stripped)
    sparql = SPARQLWrapper("http://dbpedia.org/sparql")
    # First check if this entity redirects to another entity
    sparql.setQuery("""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX db: <http://dbpedia.org/resource/>
        SELECT ?redirectsTo WHERE {
          ?x rdfs:label "%s"@en .
          ?x dbo:wikiPageRedirects ?redirectsTo
        }
    """ % words_stripped)
    sparql.setReturnFormat(JSON)
    uri_result = sparql.query().convert()['results']['bindings']
    uri = uri_result[0]['redirectsTo']['value'] if len(
        uri_result) > 0 else "http://dbpedia.org/resource/" + words_stripped.replace(' ', '_')

    sparql.setQuery(""" select ?t
                where {
                    OPTIONAL { <%s> a ?t } .
                }""" % uri)
    results = sparql.query().convert()['results']['bindings']

    def get_ontology(rs):
        # convert the resultset into a list of strings of all ontologies according to dbpedia
        ontologies = list(
            map(lambda x: x['t']['value'][28:], filter(lambda x: "http://dbpedia.org/ontology" in x['t']['value'], rs)))
        if "Person" in ontologies:
            return 'PERSON'
        elif "Organisation" in ontologies:
            return 'ORGANISATION'
        elif "Location" in ontologies:
            return 'LOCATION'
        else:
            return 'UKN'

    if 't' in results[0]:
        print('Wiki check has revealed ' + words + ' is a =>=>=> ' + get_ontology(results))
        return get_ontology(results)
    else:
        print('/!\/!\ Wiki check got no results for  ' + words)
        return 'UKN'


# =================================
# =================================
#     Check Bing for string
# =================================
# =================================

# get_url function provided on Microsoft
# https://dev.cognitive.microsoft.com/docs/services/56b43eeccf5ff8098cef3807/operations/56b4447dcf5ff8098cef380d
def send_bing(query) :
    headers = {
        # Request headers
        'Ocp-Apim-Subscription-Key': '05825610312b4aa683a9ff44ce1ae4d9',
    }

    params = urllib.parse.urlencode({
        # Request parameters
        'q': query,
        'count': '10',
        'offset': '0',
        'mkt': 'en-us',
        'safesearch': 'Moderate',
    })

    try:
        conn = http.client.HTTPSConnection('api.cognitive.microsoft.com')
        conn.request("GET", "/bing/v5.0/search?%s" % params, "{body}", headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return data
    except Exception as e:
        print("[Errno {0}] {1}".format(e.errno, e.strerror))
        return None

people_phrases = {'born', 'lived', 'died'}
organisation_phrases = {'industry', 'company', 'shares', 'chairman', 'CEO', 'stock', 'FTSE', 'DOW', 'NASDAQ'}
loc_keywords = {"Mountains", "Basin", "County", "City", "Coast", "Town", "Rey", "Avenue", "Street", "Island", "Sea",
                "Park", "Peninsula", "House", "Manor", "Tower", "North", "East", "South", "West", "United",
                "Lake", "Area", "Road"}

def bing_it(entity):
    entity_stripped = entity
    for char in string.punctuation:
        entity_stripped = entity_stripped.replace(char, '')

    url_data = send_bing(entity_stripped)

    if url_data is None:
        print('Bing failed for ' + entity)
        return 'UKN'

    # Convert to JSON
    url_data = url_data.decode("utf-8")
    url_data = json.loads(url_data)

    print(url_data)
    try:
        snippets = [i['snippet'] for i in url_data['webPages']['value']]
        if any(phrase in snippet for phrase in people_phrases for snippet in snippets):
            return 'PERSON'
        elif any(phrase in snippet for phrase in organisation_phrases for snippet in snippets):
            return 'ORGANISATION'
        elif any(phrase in snippet for phrase in loc_keywords for snippet in snippets):
            return 'LOCATION'
        else:
            return 'UKN'
    except Exception as e:
        print('There was an exception during bing! ' + entity)
        return 'UKN'




def check_bing(entity):
    return bing_it(entity)

print(check_bing('Mr. Inouye'))
# =================================
# =================================
#     Simple keyword checkers
# =================================
# =================================
# Organisations
organisations = set()
# Keywords that may appear in organisations
org_keywords = {"Co.", "Org.", "Inc.", "Inc", "Industries", "Laboratories", "Partnership", "Systems", "Group",
                "AG", "PLC", "Ltd", "Corp", "NV", "Limited", "Party", "Council", "Association", "Company", "Institute"}


def check_org(entity):
    if entity in training_organisations:
        return True
    elif entity in organisations:
        return True
    elif any(kw in entity for kw in org_keywords):
        return True
    else:
        return False

# Locations
locations = set()
# Keywords that may appear in locations
# loc_keywords = {"Mountains", "Basin", "County", "City", "Coast", "Town", "Rey", "Avenue", "Street", "Island", "Sea",
#                 "Park", "Peninsula", "House", "Manor", "Tower", "North", "East", "South", "West", "United",
#                 "Lake", "Area", "Road"}
# Already defined above in Bing section..


def check_loc(entity):
    if entity in training_locations:
        return True
    elif entity in locations:
        return True
    elif any(kw in entity for kw in loc_keywords):
        return True
    else:
        return False

# Names
people = set()
# Keywords that may appear in names
name_keywords = {"Mr", "Mrs", "Ms", "Miss", "Master", "Sir", "Lord", "Duke", "President", "Vice", "Chief", "Prof",
                 "Assistant", "Chair", "Chief", "King", "Queen", "Mayor", "Minister", "Senior", "Dr.", "Doctor", ""}
name_disallowed = {',', '(', ')', '[', '&', ' and '}


def check_people(entity, split):
    # Names all words should begin with a capital letter
    if any(map(lambda x: not x[0].isupper(), split)):
        return False
    # False if any disallowed char
    elif any(c in entity for c in name_disallowed):
        return False
    # True if entity seen in training data
    elif entity in training_people:
        return True
    # True if seen before this run
    elif entity in people:
        return True
    # False if longer than 1 word, and no family or title
    elif len(split) > 1 and not (any(x in family for x in split) or any(x in entity for x in name_keywords)):
        return False
    # True if firstname before lastname else False
    else:
        title_pos = (i for i, v in enumerate(split) if v in name_keywords).__next__() if any(word in name_keywords for word in split) else None
        firstname_pos = (i for i, v in enumerate(split) if v in firstnames).__next__() if any(word in firstnames for word in split) else None
        lastname_pos = (i for i, v in enumerate(split) if v in family).__next__() if any(word in family for word in split) else None

        if lastname_pos is not None:
            if firstname_pos is not None:
                if title_pos is not None:
                    # Title, Firstname, Lastname
                    return lastname_pos > firstname_pos > title_pos
                # Firstname, Lastname
                return lastname_pos > firstname_pos
        # Lastname alone
        # Can be only word in entity
        return len(split) == 1


def categorise(entity, split, past_entities):
    if entity in unknown:
        cat = 'UKN'
    elif not all(map(lambda x: x[0].isupper() or x[0] in str(string.punctuation), split)):
        cat = 'INV'
        unknown.add(entity)
    # If entity seen before in sentence trust it is same type
    elif any(entity in ent for ent in past_entities.keys()):
        print('Looking for superstring in past entities for ' + entity + ' in ' + str(past_entities.keys()))
        cat = (v for k, v in past_entities.items() if entity in k).__next__()
        if cat == 'LOCATION':
            locations.add(entity)
        elif cat == 'ORGANISATION':
            organisations.add(entity)
        elif cat == 'PERSON':
            people.add(entity)
        else:
            unknown.add(entity)
    elif check_loc(entity):
        cat = 'LOCATION'
        locations.add(entity)
    elif check_org(entity):
        cat = 'ORGANISATION'
        organisations.add(entity)
    elif check_people(entity, split):
        cat = 'PERSON'
        people.add(entity)
    else:
        cat = check_wiki(entity)
        # if cat == 'UKN':
        #     cat = check_bing(entity)
        #     print('Binging ' + entity + ' ===> ' + cat)

        if cat == 'LOCATION':
            locations.add(entity)
        elif cat == 'ORGANISATION':
            organisations.add(entity)
        elif cat == 'PERSON':
            people.add(entity)
        else:
            unknown.add(entity)
    return cat


def make_entity(input):
    entity = ""
    for word in input:
        if word in {'.', ','}:
            entity += word
        else:
            entity += " " + word
    return entity.strip().strip(',').strip()


def tag(entity, tag, text):
    if tag != 'UKN':
        return text.replace(entity, '<ENAMEX TYPE="' + str(tag) + '">' + entity + "</ENAMEX>")
    else:
        return text

# Unknown entities, debugging only
unknown = set()

onlyfiles = [f for f in listdir(corpus_root) if isfile(join(corpus_root, f))]

for fileid in onlyfiles:
    print(fileid)

    # Open and input and output file
    file = open(corpus_root + fileid)
    output = open(output_root + fileid, 'w')
    try:
        # Read text in input file
        text = file.read()

        # Tokenize sentence into sentences and then words
        sentences = nltk.sent_tokenize(text)
        word_sents = [nltk.word_tokenize(sent) for sent in sentences]

        # Pos tag sentences using nltk's default tagger, averaged perceptron tagger
        tagged = [nltk.pos_tag(sent) for sent in word_sents]

        for index, sent in enumerate(tagged):
            untagged = sentences[index]
            tree = cp.parse(sent)
            past_entities = dict()
            for subtree in tree.subtrees():
                if subtree.label() == "NE":
                    chunk = subtree.leaves()
                    # Unparse words to make one entity
                    # Words is passed functions because it prevents having to .split() again which is slow
                    words = [x[0] for x in chunk]

                    # Attempt to categorise the entity, if successful it will be tagged
                    entity = make_entity(words)
                    words = entity.split()
                    cat = categorise(entity, words, past_entities)
                    if cat != "UKN" and cat != "INV":
                        past_entities[entity] = cat

                    # If the detected named entity contains a conjunction
                    elif any(pos[1] == "CC" for pos in chunk):
                        print('Splitting <"' + entity + '"> on conjunction:')
                        # Split the named entity, test if any of the individual parts alone are named entities first
                        acc = []
                        ent_acc = dict()
                        for i, word in enumerate(chunk):
                            if word[1] == "CC" or word[1] == ',':
                                if len(acc) >= 1:
                                    copy = acc.copy()
                                    ent = make_entity(copy)
                                    ent_acc[ent] = copy
                                    acc.clear()
                                    print("|-----> " + ent)
                                acc.clear()
                            elif i == len(chunk)-1:
                                acc.append(word[0])
                                copy = acc.copy()
                                ent = make_entity(copy)
                                ent_acc[ent] = copy
                                acc.clear()
                                print("|-----> " + ent)
                            else:
                                acc.append(word[0])
                        # Append the last bit of accumulator to ent_acc
                        if len(acc) > 0:
                            ent
                        # If any of the smaller entities have been tagged successfully, let them be entities
                        for ent in ent_acc.items():
                            cat = categorise(ent[0], ent[1], past_entities)
                            if cat != 'UKN' and  cat != 'INV':
                                past_entities[ent[0]] = cat

            for tagged_entity in past_entities.items():
                untagged = untagged.replace(tagged_entity[0], '<ENAMEX TYPE="' + tagged_entity[1] + '">' + tagged_entity[0] + "</ENAMEX>")
            output.write(untagged)
    finally:
        file.close()
        output.close()

print("Complete: " + str(datetime.now() - startTime) + 's')
print("People: " + str(len(people)) + '(' + str(len(people.intersection(training_people))) + '/' + str(len(training_people)) + ')')
print(people)
print("Organizations: " + str(len(organisations)) + '(' + str(len(organisations.intersection(training_organisations))) + '/' + str(len(training_organisations)) + ')')
print(organisations)
print("Locations: " + str(len(locations)) + '(' + str(len(locations.intersection(training_locations))) + '/' + str(len(training_locations)) + ')')
print(locations)
print("Unknowns: " + str(len(unknown)))
print(unknown)
