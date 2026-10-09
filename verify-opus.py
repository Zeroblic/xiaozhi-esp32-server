import opuslib_next


encoder = opuslib_next.Encoder(16000, 1, opuslib_next.APPLICATION_AUDIO)
print("Opus library: OK")
