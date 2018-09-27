cores=10
#for fname in prio_10_0
for i in 85 55 50 45 40
do
    for fname in prop_10_90  prop2_10_90  prop2_30_70  prop2_50_50  prop2_70_30  prop2_90_10  prop_30_70  prop_50_50  prop_70_30  prop_90_10
    do
        echo "python main.py -i inputs/random/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=False -c False 3 >> results/our_policy_${fname}_${i}_test"
        python main.py -i inputs/random/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=False -c False 3 >> results/prop/our_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 300
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
	pgrep _r | xargs kill -9
        sleep 5
        
        echo "python main.py -i inputs/random/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True -c False 3 >> results/rapl_policy_${fname}_${i}_test"
        python main.py -i inputs/random/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True -c False 3 >> results/prop/rapl_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 300
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
	pgrep _r | xargs kill -9
        sleep 5

        echo "python main.py -i inputs/random/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True -c True 3 >> results/ourRapl_policy_${fname}_${i}_test"
        python main.py -i inputs/random/$fname --interval=1 2 --limit=$i --cores=$cores --rapl=True -c True 3 >> results/prop/ourRapl_policy_${fname}_${i}_${cores} &
        pypid=$!
        echo $pypid
        sleep 300
        kill -INT $pypid
        sleep 5
        killall python
        killall leela_r
        killall cactusBSSN_r
	pgrep _r | xargs kill -9
        sleep 5
    done
done
