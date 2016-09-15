import audioop, wave, numpy as np, tensorflow as tf
import scipy.io.wavfile as wavfile
from lib.namespace import Namespace as NS

class Dataset(object):
  def __init__(self, paths):
    self.paths = paths
    self.examples = self.load(self.paths)

  @property
  def data_dim(self):
    raise NotImplementedError()

  @property
  def filename_suffix(self):
    raise NotImplementedError()

  def dump(self, base_path, example):
    raise NotImplementedError()

  @staticmethod
  def construct(data_type, paths=None, directory=None, **kwargs):
    assert (paths is None) != (directory is None)
    if paths is None:
      paths = NS((fold, glob.glob(os.path.join(directory, "%s/*%s" % (fold, self.filename_suffix))))
                 for fold in "train valid test".split())
    return dict(wave=Wave, bytes=Bytes)[data_type](paths, **kwargs)

class Bytes(Dataset):
  @property
  def data_dim(self):
    # we just deal with any possible byte
    return 256

  @property
  def filename_suffix(self):
    return ""

  def load(self, paths):
    return NS.UnflattenLike(paths, [[list(open(path, "rb").read())] for path in NS.Flatten(paths)])

  def dump(self, base_path, example):
    sequence, = example
    with open("%s.txt" % base_path, "wb") as outfile:
      outfile.write(sequence)

class Wave(Dataset):
  def __init__(self, paths, frequency, bit_depth, **kwargs):
    """Initialize a Wav instance.

    The wav files referenced by `paths` will be made available under the
    `examples` attribute, in the same Namespace tree structure.

    Args:
      paths: Namespace tree with wav file paths
      frequency: desired sampling frequency
      bit_depth: desired amplitude resolution in bits
    """
    self.frequency = frequency
    self.bit_depth = bit_depth
    super(Wave, self).__init__(paths, **kwargs)

  @property
  def data_dim(self):
    """Number of classes."""
    return 2 ** self.bit_depth

  @property
  def filename_suffix(self):
    return ".wav"

  def load(self, paths):
    """Load data.

    Args:
      paths: Namespace tree with wav file paths

    Returns:
      Isomorphic Namespace tree with waveform examples.
    """
    return NS.UnflattenLike(paths, [[self.load_wavfile(path)] for path in NS.Flatten(paths)])

  def dump(self, base_path, example):
    """Dump a single example.

    Args:
      base_path: the path of the file to write (without extension)
      example: the waveform example to write
    """
    sequence, = example
    self.dump_wavfile("%s.wav" % base_path, sequence)

  def load_wavfile(self, path):
    """Load a single wav file.

    This is like `load_wavfile` but specifies the frequency and bit_depth.

    Args:
      path: path to the wav file to load

    Returns:
      The waveform as a sequence of categorical integers.
    """
    return load_wavfile(path, bit_depth=self.bit_depth, frequency=self.frequency)

  def dump_wavfile(self, path, sequence):
    """Dump a single wav file.

    This is like `dump_wavfile` but specifies the frequency and bit_depth.

    Args:
      path: where to dump the wav file.
      sequence: the sequence to dump.
    """
    dump_wavfile(path, sequence, frequency=self.frequency, bit_depth=self.bit_depth)

def load_wavfile(path, bit_depth, frequency):
  """Load a wav file.

  Resamples the wav file to have sampling frequency `frequency`. The waveform
  is converted to mono, normalized, and its amplitude is discretized into
  `2 ** bit_depth` bins.

  Args:
    path: path to the wav file to load
    bit_depth: resolution of the amplitude discretization, in bits
    frequency: desired sampling frequency

  Returns:
    The waveform as a sequence of categorical integers.
  """
  wav = wave.open(path)
  x = wav.readframes(wav.getnframes())

  # convert to mono
  if wav.getnchannels() > 1:
    x = audioop.tomono(x, wav.getsampwidth(), 0.5, 0.5)

  # convert sampling rate
  x, _ = audioop.ratecv(x, wav.getsampwidth(), 1, wav.getframerate(), frequency, None)

  # center and normalize (done in np.float32 to avoid loss of precision)
  dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[wav.getsampwidth()]
  x = np.frombuffer(x, dtype).astype(np.float32)
  x -= x.mean()
  max_amplitude = abs(x).max()
  # if this happens i'd like to know about it
  assert max_amplitude > 0
  x /= max_amplitude

  x = ulaw(x, mu=bit_depth - 1)
  x = ((2 ** bit_depth - 1) * (x + 1) / 2).round().astype(np.int32)

  return x

def dump_wavfile(path, x, bit_depth, frequency):
  """Dump a wav file.

  Interprets the sequence of integers `x` as a discretized waveform with
  `2 ** bit_depth` amplitude levels and sampling frequency `frequency`,
  and writes the waveform to a mono wav file.

  Args:
    path: path to the wav file to write
    x: the sequence to convert and dump
    bit_depth: resolution of the amplitude discretization, in bits
    frequency: sampling frequency
  """
  x = np.asarray(x, np.float32) / 2 ** bit_depth * 2 - 1
  x = inverse_ulaw(x, mu=bit_depth - 1)
  wavfile.write(path, frequency, x)

def ulaw(x, mu=255):
  return np.sign(x) * np.log(1 + mu * np.abs(x)) / np.log(1 + mu)

def inverse_ulaw(y, mu=255):
  return np.sign(y) / mu * ((1 + mu) ** np.abs(y) - 1)