TopModule: process (a, b, sel) begin if (sel=0) then out_p <= a; else out_p <= b; end if; end process;
