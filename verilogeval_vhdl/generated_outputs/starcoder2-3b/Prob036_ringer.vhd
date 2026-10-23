TopModule: Circuit_2_1 port map(ring, vibrate_mode, ringer, motor); if(ring = '1') then if(vibrate_mode = '1') then motor <= '1'; ringer <= '0'; else ringer <= '1'; motor <= '0'; end if; end if;
