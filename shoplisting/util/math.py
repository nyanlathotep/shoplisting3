import string
import math

class AlphaBase():
  def __init__(self, alpha):
    self.base = len(alpha)
    self.bps = math.log(self.base, 2)
    self.symbols = {}
    self.rev_symbols = {}
    for i in range(len(alpha)):
      self.symbols[i] = alpha[i]
      self.rev_symbols[alpha[i]] = i
  def _to_base_int(self, n):
    s = ''
    if n == 0:
      return self.symbols[0]
    while (n > 0):
      rem = n % self.base
      s = self.symbols[rem] + s
      n = (n - rem) // self.base
    return(s)
  def _to_base_bytes(self, b):
    bits = 0
    buffer = 0
    octets = iter(b)
    go = True
    s = []
    while go:
      while bits < self.bps:
        try:
          o = octets.__next__()
          buffer *= 256; buffer += o
          bits += 8
        except StopIteration:
          go = False
          break
      while bits > self.bps:
        rem = buffer % self.base
        s.append(self.symbols[rem])
        buffer = (buffer - rem) // self.base
        bits -= self.bps
    while buffer > 0:
      rem = buffer % self.base
      s.append(self.symbols[rem])
      buffer = (buffer - rem) // self.base
    return s[::-1]
  def to_base(self, v):
    if isinstance(v, int):
      return self._to_base_int(v)
    elif isinstance(v, bytes):
      return self._to_base_bytes(v)
    else:
      raise ValueError
  def from_base(self, s):
    n = 0
    for c in s:
      n *= self.base
      n += self.rev_symbols[c]
    return(n)
  def bytes_from_base(self, s):
    buffer = 0
    bits = 0
    b = []
    for c in s[::-1]:
      buffer *= self.base; buffer += self.rev_symbols[c]; bits += self.bps
      while bits > 8:
        rem = buffer % 256
        b.append(rem); buffer = (buffer - rem) // 256; bits -= 8
    while buffer > 0:
      rem = buffer % 256
      b.append(rem); buffer = (buffer - rem) // 256
    return bytes(b[::-1])

base36 = AlphaBase(string.digits+string.ascii_lowercase)
