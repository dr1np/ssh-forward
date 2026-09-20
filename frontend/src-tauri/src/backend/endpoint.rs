pub fn format_endpoint(host: &str, port: u32) -> String {
    let value = host.trim();
    let display_host = if value.contains(':') && !(value.starts_with('[') && value.ends_with(']')) {
        format!("[{value}]")
    } else {
        value.to_string()
    };
    format!("{display_host}:{port}")
}

#[cfg(test)]
mod tests {
    use super::format_endpoint;

    #[test]
    fn formats_ipv4_without_brackets() {
        assert_eq!(format_endpoint("127.0.0.1", 8080), "127.0.0.1:8080");
    }

    #[test]
    fn brackets_ipv6_hosts() {
        assert_eq!(format_endpoint("::1", 8080), "[::1]:8080");
        assert_eq!(format_endpoint("2001:db8::1", 443), "[2001:db8::1]:443");
    }

    #[test]
    fn preserves_already_bracketed_hosts() {
        assert_eq!(format_endpoint("[::1]", 8080), "[::1]:8080");
    }

    #[test]
    fn formats_a_forward_spec_with_ipv6_brackets() {
        assert_eq!(
            super::format_forward_spec("::1", 8080, "2001:db8::1", 443),
            "[::1]:8080:[2001:db8::1]:443",
        );
    }
}

pub fn format_forward_spec(
    local_bind: &str,
    local_port: u32,
    remote_host: &str,
    remote_port: u32,
) -> String {
    format!(
        "{}:{}",
        format_endpoint(local_bind, local_port),
        format_endpoint(remote_host, remote_port)
    )
}
