# Creator modes

## Fast
Full-quality scene images with local cinematic motion and transitions.

## Balanced
Animates about half of the most important scenes. Failed animated scenes fall back individually to cinematic still motion.

## Cinematic
Animates every semantic scene. Compatible continuous transitions may use start and end keyframes.

## Pipeline
Plan -> 1024x1536 images -> narration -> exact scene timing -> selected scene animation -> captions -> 720x1280/30fps montage -> music ducking -> single delivery.

Animated clips are cached for one hour. Temporary creator folders are retained for one hour. The local animation service receives reference images directly because both services run on the same computer; this is faster than an external upload and does not reduce quality.
