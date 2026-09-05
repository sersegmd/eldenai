from pathlib import Path
import importlib.util,sys
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('creator_modes',root/'app/creator_modes.py');m=importlib.util.module_from_spec(spec);sys.modules['creator_modes']=m;spec.loader.exec_module(m)
scenes=[{'importance':.9,'motion_prompt':'camera orbit'},{'importance':.1},{'importance':.8,'motion_prompt':'tracking move'},{'importance':.3}]
assert m.animated_scene_indices('fast',scenes)==[]
assert len(m.animated_scene_indices('balanced',scenes))==2
assert m.animated_scene_indices('cinematic',scenes)==[0,1,2,3]
c=(root/'app/creator.py').read_text();a=(root/'app/scene_animator.py').read_text();d=(root/'app/delivery.py').read_text()
assert 'asplit=2[voice_sidechain][voice_mix]' in c
assert 'animate_creator_scenes' in c
assert all(f'creator_mode:{x}' in c for x in ('fast','balanced','cinematic'))
assert 'reference_image' in a and 'end_frame_image' in a
assert '768x768' in c
assert "url=f'https://api.telegram.org/bot{settings.bot_token}/{m}'" in d
assert "url=f'{{https://" not in d
print('Creator modes/animation/single-delivery: PASS')
