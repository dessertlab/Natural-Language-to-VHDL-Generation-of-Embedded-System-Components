module TopModule is port(in_p: in std_logic_vector(7 downto 0); pos: out std_logic_vector(2 downto 0)); end TopModule; pos <= in_p(0) & in_p(1) & in_p(2);
