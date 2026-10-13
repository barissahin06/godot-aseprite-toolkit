import unittest

from pixelspark_art_mcp.assets import animation_specs, sprite_frames


class FrameAnimationTests(unittest.TestCase):
    def setUp(self):
        self.data = {'frames': [{'duration': ms, 'frame': {'x': index*8, 'y': 0, 'w': 8, 'h': 8}}
                               for index, ms in enumerate([100, 80, 120])],
                     'meta': {'frameTags': [{'name': 'attack', 'from': 0, 'to': 2}]}}

    def test_single_attack_keeps_timing_and_markers(self):
        options = {'attack': {'loop': False, 'markers': {'contact': .18, 'chain_ready': .26}}}
        clip = animation_specs(self.data, options)[0]
        self.assertEqual(clip['durations'], [.1, .08, .12])
        self.assertEqual(clip['seconds'], .3)
        self.assertFalse(clip['loop'])
        self.assertEqual(clip['markers'], options['attack']['markers'])
        self.assertIn('"loop": false', sprite_frames('res://sheet.png', self.data, options))
        self.assertIn('"loop": true', sprite_frames('res://sheet.png', self.data))

    def test_invalid_animation_settings_fail(self):
        invalid = [{'missing': {}}, {'attack': {'loop': 'false'}},
                   {'attack': {'markers': {'contact': .31}}},
                   {'attack': {'markers': {'contact': float('nan')}}},
                   {'attack': {'markers': {'contact': True}}},
                   {'attack': {'markers': {'contact': .18, 'chain_ready': .18}}}]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ValueError):
                animation_specs(self.data, options)

    def test_reverse_and_pingpong_durations_follow_texture_order(self):
        tag = self.data['meta']['frameTags'][0]
        tag['direction'] = 'reverse'
        self.assertEqual(animation_specs(self.data)[0]['durations'], [.12, .08, .1])
        tag['direction'] = 'pingpong'
        self.assertEqual(animation_specs(self.data)[0]['indices'], [0,1,2,1])
        self.assertEqual(animation_specs(self.data)[0]['durations'], [.1,.08,.12,.08])
