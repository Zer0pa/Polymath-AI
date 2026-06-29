package ai.zer0pa.polymath.lab.data

import ai.zer0pa.polymath.lab.domain.RunId
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

fun newUtcRunId(): RunId {
    val format = SimpleDateFormat("yyyy-MM-dd'T'HHmmss'Z'", Locale.US)
    format.timeZone = TimeZone.getTimeZone("UTC")
    return RunId(format.format(Date()))
}
