TopModule: inputs <= std_logic_vector(d); q <= std_logic_vector(d); for i in 0 to 7 loop DFF_Module_i: DFF port map (clk, rst, q(i), q(i)); end loop;
