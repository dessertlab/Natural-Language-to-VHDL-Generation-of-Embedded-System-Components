TopModule: in_p : in 32 bit; out_p : out 32 bit; signal tmp : std_logic_vector(31 downto 0); begin process (in_p) begin tmp := in_p(31 downto 0); out_p <= tmp; end process tmp; end TopModule;
