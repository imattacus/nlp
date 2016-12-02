from os import listdir
from os.path import isfile, join
import re
from collections import defaultdict
from nltk import pos_tag, word_tokenize
import pickle


class TagExtractor:
    tagged_corpus = ''
    only_files = []
    loc_tag_sequences = defaultdict(int)
    per_tag_sequences = defaultdict(int)
    org_tag_sequences = defaultdict(int)
    named_entities_root = "/Users/mattcallaway/nltk_data/corpora/named_entities/"
    organizations = open(named_entities_root + 'organizations.txt', 'w')
    people = open(named_entities_root + 'people.txt', 'w')
    locations = open(named_entities_root + 'locations.txt', 'w')
    grammar = open(named_entities_root + 'grammar.txt', 'w')
    grammar_likeliness = open(named_entities_root + 'likeliness.txt', 'w')
    disallowed_tags = {"(", ")", ":"}
    allowed_tags = {"NNP", "NNPS", ".", "CC", "NN", "NNS"}

    def __init__(self, training_data):
        self.tagged_corpus = training_data
        self.only_files = [f for f in listdir(self.tagged_corpus) if isfile(join(self.tagged_corpus, f))]

    def extract(self):
        organizations = set()
        people = set()
        locations = set()
        for fileid in self.only_files:
            print(fileid)
            file = open(self.tagged_corpus + fileid)
            text = file.read()

            docsPattern = r'<ENAMEX TYPE="(\w+)">(.*?)</ENAMEX>'
            docTuples = re.findall(docsPattern, text, re.DOTALL)
            for named_entity in docTuples:
                type = named_entity[0]
                content = named_entity[1]

                tagged = pos_tag(word_tokenize(content))

                tag_seq = tuple(i[1] for i in tagged)

                if type == "ORGANIZATION":
                    self.org_tag_sequences[tag_seq] += 1
                    organizations.add(content)
                elif type == "LOCATION":
                    self.loc_tag_sequences[tag_seq] += 1
                    locations.add(content)
                elif type == "PERSON":
                    self.per_tag_sequences[tag_seq] += 1
                    people.add(content)
        self.organizations.write("\n".join(sorted(organizations)))
        self.locations.write("\n".join(sorted(locations)))
        self.people.write("\n".join(sorted(people)))

    def save_grammar(self):
        # Combine all grammars to one named entity grammar
        def combine_grammar(a, b):
            for k, v in b.items():
                a[k] += v
            return a

        all_tag_sequences = combine_grammar(combine_grammar(self.loc_tag_sequences, self.org_tag_sequences), self.per_tag_sequences)

        def sort_grammar(grammar):
            desc_grammar = [pair[0] for pair in sorted(grammar.items(), key=lambda item: item[1])]
            most_freq = desc_grammar[int(len(desc_grammar) * 0.25):]
            return sorted(most_freq, key=lambda item: len(item), reverse=True)

        def write_grammar(tag, grammar):
            for rule in grammar:
                if set(rule).issubset(self.allowed_tags):
                    if 'NN' in rule or 'NNS' in rule and not len(rule) > 1:
                        continue
                    else:
                        self.grammar.write(tag + ': ')
                        self.grammar.write("{<")
                        self.grammar.write("><".join(rule))
                        self.grammar.write(">}\n")

        # def likeliness(rule):
        #     d = {
        #         'PER': self.per_tag_sequences[rule],
        #         'ORG': self.org_tag_sequences[rule],
        #         'LOC': self.loc_tag_sequences[rule]
        #     }
        #     ans = max(d, key=d.get)
        #     print(str(rule) + ' ' + str(d) + ' :' + ans)
        #     return ans
        #
        # def save_likeliness_dict(grammar):
        #     l = {}
        #     for rule in grammar:
        #         if set(rule).issubset(self.allowed_tags):
        #             l[rule] = likeliness(rule)
        #     pickle.dump(l, open('likeliness_dict.pkl', 'wb'))

        grammar = sort_grammar(all_tag_sequences)
        write_grammar('NE', grammar)
        # save_likeliness_dict(grammar)

if __name__ == "__main__":
    training_root = "/Users/mattcallaway/nltk_data/corpora/wsj_training/"
    tag_extractor = TagExtractor(training_data=training_root)
    tag_extractor.extract()
    tag_extractor.save_grammar()
