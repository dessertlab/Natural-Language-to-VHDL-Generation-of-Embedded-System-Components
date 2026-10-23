with in_p select out_both(99 downto 0) <= in[99] & in[98]; out_any(2 downto 0) <= in(2 downto 1) & in(1); out_different(99 downto 0) <= in(98) & in(0); end select;
