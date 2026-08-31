const HEADER_BYTES = 44;

function writeAscii(view: DataView, offset: number, value: string): void {
  for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
}

export function encodePcm16Wav(audio: AudioBuffer): Blob {
  const channels = audio.numberOfChannels; const frames = audio.length;
  const bytesPerSample = 2; const dataBytes = frames * channels * bytesPerSample;
  const buffer = new ArrayBuffer(HEADER_BYTES + dataBytes); const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF"); view.setUint32(4, 36 + dataBytes, true); writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, channels, true); view.setUint32(24, audio.sampleRate, true);
  view.setUint32(28, audio.sampleRate * channels * bytesPerSample, true);
  view.setUint16(32, channels * bytesPerSample, true); view.setUint16(34, 16, true);
  writeAscii(view, 36, "data"); view.setUint32(40, dataBytes, true);
  const samples = Array.from({ length: channels }, (_, channel) => audio.getChannelData(channel));
  let offset = HEADER_BYTES;
  for (let frame = 0; frame < frames; frame += 1) for (const channel of samples) {
    const sample = Math.max(-1, Math.min(1, channel[frame] ?? 0));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true); offset += bytesPerSample;
  }
  return new Blob([buffer], { type: "audio/wav" });
}
