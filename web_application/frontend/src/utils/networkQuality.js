/**
 * Returns the default quality for playback.
 * Always picks the lowest available quality (480p if present) so users
 * start with fast-loading video and can manually upgrade if desired.
 *
 * @param {string[]} availableQualities - Quality labels present on the server, ordered high→low
 * @returns {string} The lowest available quality label
 */
export function detectNetworkQuality(availableQualities = ['1080p', '720p', '480p']) {
  return availableQualities.at(-1) ?? '480p';
}
