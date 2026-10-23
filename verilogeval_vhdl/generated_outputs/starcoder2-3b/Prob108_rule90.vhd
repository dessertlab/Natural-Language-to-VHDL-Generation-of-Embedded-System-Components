import TopModule : Circuit(clk, load, data, q) begin for i in 0 to 511 loop if q(i) = '1' then q(i+1) <= '1' xor q(i-1) xor q(i+2); end if; end loop; q(511) <= '0'; end Behavioral;
