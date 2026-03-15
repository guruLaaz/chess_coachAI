/**
 * Translates server progress messages into the current locale.
 * Ported from _tMsg() in web/templates/partials/controls.html.
 *
 * @param {string} serverMsg - Raw message from the status JSON endpoint
 * @param {Function} t - The vue-i18n t() function
 * @returns {string} Translated message (falls back to original if no match)
 */
export function translateMessage(serverMsg, t) {
  if (!serverMsg) return ''

  // "Fetching Chess.com games... (200/2280)"
  const fetchCountMatch = serverMsg.match(
    /^Fetching (Chess\.com|Lichess) games\.\.\.\s*\((\d+)\/(\d+)\)$/,
  )
  if (fetchCountMatch) {
    const key =
      fetchCountMatch[1] === 'Chess.com'
        ? 'status_fetching_chesscom'
        : 'status_fetching_lichess'
    return t(key) + ' (' + fetchCountMatch[2] + '/' + fetchCountMatch[3] + ')'
  }

  // "Fetching Chess.com games..." / "Fetching Lichess games..."
  if (/^Fetching Chess\.com games/.test(serverMsg))
    return t('status_fetching_chesscom')
  if (/^Fetching Lichess games/.test(serverMsg))
    return t('status_fetching_lichess')

  // "Analyzing game 5/120..."
  const analyzeMatch = serverMsg.match(/^Analyzing game (\d+)\/(\d+)/)
  if (analyzeMatch)
    return t('status_analyzing_game') + ' ' + analyzeMatch[1] + '/' + analyzeMatch[2] + '\u2026'

  // "Fetching Chess.com archive 3/12 (150 games)"
  const archiveMatch = serverMsg.match(
    /^Fetching Chess\.com archive (\d+)\/(\d+) \((\d+) games\)$/,
  )
  if (archiveMatch)
    return (
      t('status_fetching_archive') +
      ' ' +
      archiveMatch[1] +
      '/' +
      archiveMatch[2] +
      ' (' +
      archiveMatch[3] +
      ' ' +
      t('eg_games_suffix') +
      ')'
    )

  // "Fetched 200 Lichess games"
  const fetchedLiMatch = serverMsg.match(/^Fetched (\d+) Lichess games$/)
  if (fetchedLiMatch)
    return t('status_fetched_lichess', { 0: fetchedLiMatch[1] })

  // "Fetched 500 games, starting analysis"
  const fetchedStartMatch = serverMsg.match(
    /^Fetched (\d+) games, starting analysis$/,
  )
  if (fetchedStartMatch)
    return t('status_fetched_starting', { 0: fetchedStartMatch[1] })

  // "Endgame analysis complete, starting openings"
  if (serverMsg === 'Endgame analysis complete, starting openings')
    return t('status_endgame_done')

  // "All games cached, skipping engine analysis"
  if (serverMsg === 'All games cached, skipping engine analysis')
    return t('status_all_cached')

  // "Analysis complete: 500 games"
  const completeMatch = serverMsg.match(/^Analysis complete: (\d+) games$/)
  if (completeMatch)
    return t('status_analysis_done', { 0: completeMatch[1] })

  // "No games found."
  if (serverMsg === 'No games found.') return t('status_no_games')

  return serverMsg
}
