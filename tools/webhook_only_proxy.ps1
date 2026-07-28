param(
    [int]$Port = 8790,
    [string]$Target = "http://127.0.0.1:8788/api/communications/whatsapp/webhook"
)

$ErrorActionPreference = "Stop"

$listener = [System.Net.HttpListener]::new()
$prefix = "http://127.0.0.1:$Port/"
$listener.Prefixes.Add($prefix)
$listener.Start()

Write-Host "BITORA webhook-only proxy activo en $prefix" -ForegroundColor Cyan
Write-Host "Destino permitido: $Target" -ForegroundColor Gray
Write-Host "Solo se acepta /api/communications/whatsapp/webhook" -ForegroundColor Gray

function Send-Text {
    param($Response, [int]$Status, [string]$Text)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $Response.StatusCode = $Status
    $Response.ContentType = "text/plain; charset=utf-8"
    $Response.ContentLength64 = $bytes.Length
    $Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $Response.OutputStream.Close()
}

try {
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response
        try {
            if ($request.Url.AbsolutePath -ne "/api/communications/whatsapp/webhook") {
                Send-Text $response 404 "BITORA webhook proxy: ruta no permitida"
                continue
            }

            $targetUri = $Target
            if ($request.Url.Query) {
                $targetUri += $request.Url.Query
            }

            $webRequest = [System.Net.HttpWebRequest]::Create($targetUri)
            $webRequest.Method = $request.HttpMethod
            $webRequest.Timeout = 30000
            $webRequest.AllowAutoRedirect = $false
            foreach ($headerName in $request.Headers.AllKeys) {
                if ($headerName -in @("Host", "Content-Length", "Connection", "Expect")) {
                    continue
                }
                try {
                    $webRequest.Headers[$headerName] = $request.Headers[$headerName]
                } catch {
                    # Algunos encabezados restringidos los administra HttpWebRequest.
                }
            }

            if ($request.HasEntityBody) {
                $bodyStream = $webRequest.GetRequestStream()
                $request.InputStream.CopyTo($bodyStream)
                $bodyStream.Close()
            }

            try {
                $upstream = $webRequest.GetResponse()
            } catch [System.Net.WebException] {
                $upstream = $_.Exception.Response
            }

            if ($null -eq $upstream) {
                Send-Text $response 502 "BITORA webhook proxy: upstream no disponible"
                continue
            }

            $response.StatusCode = [int]$upstream.StatusCode
            $response.ContentType = $upstream.ContentType
            $stream = $upstream.GetResponseStream()
            $stream.CopyTo($response.OutputStream)
            $stream.Close()
            $upstream.Close()
            $response.OutputStream.Close()
        } catch {
            Send-Text $response 500 "BITORA webhook proxy: error controlado"
        }
    }
} finally {
    if ($listener.IsListening) {
        $listener.Stop()
    }
    $listener.Close()
}
