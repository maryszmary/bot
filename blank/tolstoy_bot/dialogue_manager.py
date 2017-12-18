# -*- coding: utf-8 -*-
"""
This file contains the main class for dialogue management.
This class is messenger-agnostic, ang could be reused with VK, WhatsApp, etc.
"""
import pandas as pd
import numpy as np

# todo: introduce specific MESSAGE and RESPONSE objects, messenger-agnostic.
# this way, main.py does not have to parse reactions.


class StupidLinearDialogue:
    """ Handler of primitive sequential dialogues.
    """
    script = None   # dataframe with the whole scenario
    config = None   # dict with additional setup data
    position = 0    # index of current state of the bot (its last action)
    default_negative_response = None
    default_pause = 5
    count = 0
    location_matcher = None
    
    def __init__(self, script):
        """ 
        Parameters:
        script: pd.DataFrame keyed by ['action', 'reaction',
            'tag', 'next_tags', 'negative_reaction']
        """
        self.script = script
        self.reset()
    
    def reset(self):
        """ Roll back the bot state """
        self.position = 0  # последнее завершённое действие
        self.count = self.script.shape[0]
        # parse next positions - they are lists of indices
        # by default, next position is next index (the 1st, for the last row).
        self.script['candidate_positions'] = [[i] for i in list(range(1, self.count)) + [0]]
        if 'next_tags' in self.script and 'tag' in self.script:
            tags = self.script.tag.dropna().astype(str)
            tag2index = tags.reset_index().set_index('tag')['index'].to_dict()

            def find_indices(tags):
                return [tag2index[t] for t in tags.split('|')]
            candidates = self.script.next_tags.dropna().apply(find_indices)
            self.script['candidate_positions'].update(candidates)
        # fill empty actions and reactions
        for c in ['action', 'reaction']:
            self.script[c] = self.script[c].fillna('').astype(str)

    def next(self, message):
        """ Move along the strictly linear dialogue, independently of user actions.
        """
        if self.position >= self.count:
            self.reset()
            return "Сценарий завершён. Начинаю заново. Таково колесо сансары."
        response = self.script.loc[self.position, 'reaction']
        self.position += 1
        return response
    
    def react(self, action):
        """ Read action, reset state, and return response in a text form.
            action: a raw Telebot message from user, or an event generated by timer.
        """
        response = ''
        for cand_pos in self.script.loc[self.position, 'candidate_positions']:
            if self.is_valid_action(self.script.loc[cand_pos, 'action'], action):
                response = self.script.loc[cand_pos, 'reaction']
                self.position = cand_pos
                break
        if response == '':
            response = self.get_negative_response(self.position)
        return response
    
    def get_negative_response(self, position):
        # by default, repeat previous message
        specific = self.script.loc[position, 'negative_reaction']
        if self.is_valid_string(specific):
            return specific
        elif self.is_valid_string(self.default_negative_response):
            return self.default_negative_response
        return self.script.loc[self.position, 'reaction']
    
    def is_valid_action(self, expected, real):
        if expected.startswith('/'):
            # parse Telegram commands
            return True
        elif expected.startswith('['):
            # todo: allow multiple commands or mix of commands and words
            # parse specific commands
            if expected in {'[anytext]', '[initial]'}:
                return True
            elif expected.startswith('[pause'):
                # todo: check if the pause has not ended yet
                # Maybe just check HOW MANY times this was asked.
                return True
            elif expected.startswith('[location'):
                if self.location_matcher is None:
                    # не могу заматчить локацию, так что возвращаю True
                    return True
                # todo: parse location
        else:
            # check if input equals one of pattern words
            texts = [s.strip() for s in expected.lower().split('|')]
            # todo: allow synonym matching, RE, spelling correction, etc.
            return real.text.lower().strip() in texts

    def is_valid_string(self, s):
        return type(s) is str and len(s) > 0


    def needs_proactive(self):
        """ Check whether this dialogue is waiting to go on after a pause. """
        for cand_pos in self.script.loc[self.position, 'candidate_positions']:
            if '[pause' in str(self.script.loc[cand_pos, 'action']):
                return True
        return False
