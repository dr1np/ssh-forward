use std::env;
use std::io::Write;
use std::net::TcpListener;
use std::process;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.last().is_some_and(|value| value == "fail") {
        let _ = writeln!(std::io::stderr(), "simulated authentication failure");
        process::exit(7);
    }

    let spec = args
        .iter()
        .position(|value| value == "-L")
        .and_then(|index| args.get(index + 1))
        .cloned()
        .unwrap_or_default();
    let (bind, port) = parse_local_endpoint(&spec).unwrap_or_else(|| {
        let _ = writeln!(
            std::io::stderr(),
            "invalid forwarding specification: {spec}"
        );
        process::exit(8);
    });
    let listener = TcpListener::bind((bind.as_str(), port)).unwrap_or_else(|error| {
        let _ = writeln!(std::io::stderr(), "cannot bind {bind}:{port}: {error}");
        process::exit(9);
    });
    for stream in listener.incoming() {
        if let Ok(mut stream) = stream {
            let _ = stream.write_all(b"test-helper\n");
        }
    }
}

fn parse_local_endpoint(spec: &str) -> Option<(String, u16)> {
    let (host, rest) = if let Some(rest) = spec.strip_prefix('[') {
        let end = rest.find(']')?;
        (
            rest[..end].to_string(),
            rest.get(end + 1..)?.strip_prefix(':')?,
        )
    } else {
        let end = spec.find(':')?;
        (spec[..end].to_string(), spec.get(end + 1..)?)
    };
    let end = rest.find(':')?;
    Some((host, rest[..end].parse().ok()?))
}
