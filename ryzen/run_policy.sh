for i in  25 35 70
do
    for fname in iprio80 iprio82 iprio86 iprio84
    do
          echo "python main.py -i inputs/$fname --interval=1 2 --limit=$i --core=8 >> results/policy_${fname}_${i}_8"
          python main.py -i inputs/$fname --interval=1 2 --limit=$i --cores=8 >> final/fixed_policy_prio_${fname}_${i}_8 &
          pypid=$!
          echo $pypid
          sleep 300
          kill -INT $pypid
          sleep 5
          killall python
          killall cactusBSSN_r
          killall perlbench_r
          sleep 5
    done
done

