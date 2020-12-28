import base64
import collections
import io
import subprocess
import sys
from operator import itemgetter

import ffmpeg
import webrtcvad
import numpy as np
import soundfile as sf

from .frame import Frame

sample_rate = 16000
frame_duration_ms = 30
padding_duration_ms = 300
max_duration = 15
min_duration = 2


def wav_data_to_wav_content(wav_data_bytes):
    """Generate wav file content from wav data

    Takes wav file data and add wav header to generate wav content.
    """
    wav_data_arr = np.frombuffer(wav_data_bytes, dtype=np.int16)
    wav_content = io.BytesIO()
    sf.write(wav_content, wav_data_arr, 16000, format='wav')
    wav_content.seek(0)
    return wav_content.read()


def wav_content_to_wav_data(wav_content):
    """Read wav file and extract data

    Take wav file content and extract wav data.
    """
    wav_content = io.BytesIO(wav_content)
    data, sr = sf.read(wav_content, dtype=np.int16)
    return data.tobytes()


def frame_generator(wav_data, timestamp_offset):
    """Generates audio frames from PCM audio data.

    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.

    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = timestamp_offset
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(wav_data):
        yield Frame(wav_data[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


def vad_collector_result(voiced_frames):
    start = voiced_frames[0].timestamp
    end = voiced_frames[-1].timestamp
    return {
        'start': start,
        'end': end,
        'duration': end - start,
        'data': b''.join([f.bytes for f in voiced_frames])
    }


def vad_collector(vad, frames):
    """Filters out non-voiced audio frames.

    Given a webrtcvad.Vad and a source of audio frames, yields only
    the voiced audio.

    Uses a padded, sliding window algorithm over the audio frames.
    When more than 90% of the frames in the window are voiced (as
    reported by the VAD), the collector triggers and begins yielding
    audio frames. Then the collector waits until 90% of the frames in
    the window are unvoiced to detrigger.

    The window is padded at the front and back to provide a small
    amount of silence or the beginnings/endings of speech around the
    voiced frames.

    Arguments:

    vad - An instance of webrtcvad.Vad.
    frames - a source of audio frames (sequence or generator).

    Returns: A generator that yields PCM audio data.
    """
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    # We use a deque for our sliding window/ring buffer.
    ring_buffer = collections.deque(maxlen=num_padding_frames)
    # We have two states: TRIGGERED and NOTTRIGGERED. We start in the
    # NOTTRIGGERED state.
    triggered = False

    voiced_frames = []
    for frame in frames:
        is_speech = vad.is_speech(frame.bytes, sample_rate)

        if not triggered:
            ring_buffer.append((frame, is_speech))
            num_voiced = len([f for f, speech in ring_buffer if speech])
            # If we're NOTTRIGGERED and more than 90% of the frames in
            # the ring buffer are voiced frames, then enter the
            # TRIGGERED state.
            if num_voiced > 0.7 * ring_buffer.maxlen:
                triggered = True
                # We want to yield all the audio we see from now until
                # we are NOTTRIGGERED, but we have to start with the
                # audio that's already in the ring buffer.
                for f, s in ring_buffer:
                    voiced_frames.append(f)
                ring_buffer.clear()
        else:
            # We're in the TRIGGERED state, so collect the audio data
            # and add it to the ring buffer.
            voiced_frames.append(frame)
            ring_buffer.append((frame, is_speech))
            num_unvoiced = len([f for f, speech in ring_buffer if not speech])
            # If more than 90% of the frames in the ring buffer are
            # unvoiced, then enter NOTTRIGGERED and yield whatever
            # audio we've collected.
            if num_unvoiced > 0.7 * ring_buffer.maxlen:
                triggered = False
                yield vad_collector_result(voiced_frames)
                ring_buffer.clear()
                voiced_frames = []

    # If we have any leftover voiced audio when we run out of input,
    # yield it.
    if voiced_frames:
        yield vad_collector_result(voiced_frames)


def recursive_vad(result, aggressiveness=0):
    if aggressiveness >= 4:
        return []

    vad = webrtcvad.Vad(aggressiveness)
    frames = frame_generator(result['data'], result['start'])
    segments = vad_collector(vad, frames)

    result = []
    for segment in segments:
        if segment['duration'] < max_duration:
            segment['aggressiveness'] = aggressiveness
            result.append(segment)
        else:
            result.extend(recursive_vad(segment, aggressiveness + 1))
    return result


def vad_file(av_filepath):
    with open(av_filepath, 'rb') as f:
        av_content = f.read()
    return vad(av_content)


def vad(av_content):
    args = (
        ffmpeg
        .input('pipe:')
        .output(
            'pipe:',
            format='wav',
            acodec='pcm_s16le',
            ac=1,
            ar=sample_rate
        )
        .get_args()
    )
    ffmpeg_process = subprocess.Popen(
        ['ffmpeg'] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    wav_content = ffmpeg_process.communicate(input=av_content)[0]
    ffmpeg_process.kill()
    wav_data = wav_content_to_wav_data(wav_content)
    duration = len(wav_data) / (sample_rate * 2)
    init_point = {
        'start': 0,
        'end': duration,
        'duration': duration,
        'data': wav_data
    }
    segments = recursive_vad(init_point)
    segments.sort(key=itemgetter('start'))
    return [
        {
            'start': segment['start'],
            'end': segment['end'],
            'duration': segment['duration'],
            'aggressiveness': segment['aggressiveness'],
            'data': base64.b64encode(segment['data'])
        }
        for segment in segments
        if segment['duration'] > min_duration
    ]


if __name__ == '__main__':
    # vad_file('/home/aj/repo/vad/resources/shah.mp3')
    result = vad_file('/home/aj/repo/vad/resources/taste_of_cherry.mp4')
