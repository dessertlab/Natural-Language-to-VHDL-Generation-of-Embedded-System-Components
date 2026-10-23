TopModule : in  x3 : in STD_LOGIC; in  x2 : in STD_LOGIC; in  x1 : in STD_LOGIC; out f : out STD_LOGIC; begin process (x3, x2, x1) begin f <= x3 or x2 or x1; end process ; end TopModule;
